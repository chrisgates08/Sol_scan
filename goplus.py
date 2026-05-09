import httpx
import hashlib
import time as time_module
from config import GOPLUS_APP_KEY, GOPLUS_APP_SECRET

GOPLUS_BASE = "https://api.gopluslabs.io"

# Cache de l'access_token pour éviter de le régénérer à chaque appel
_access_token_cache = {
    "token": None,
    "expires_at": 0
}

async def _get_access_token() -> str | None:
    """
    Étape 1 de l'auth GoPlus :
    POST /api/v1/token
    Body: { app_key, time, sign: sha1(app_key + time + app_secret) }
    Retourne un access_token valide, mis en cache.
    """
    if not GOPLUS_APP_KEY or not GOPLUS_APP_SECRET:
        return None

    now = _access_token_cache
    # Réutilise le token s'il est encore valide (marge de 60s)
    if now["token"] and time_module.time() < now["expires_at"] - 60:
        return now["token"]

    timestamp = int(time_module.time())
    raw       = f"{GOPLUS_APP_KEY}{timestamp}{GOPLUS_APP_SECRET}"
    sign      = hashlib.sha1(raw.encode()).hexdigest()

    payload = {
        "app_key": GOPLUS_APP_KEY,
        "time":    timestamp,
        "sign":    sign,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{GOPLUS_BASE}/api/v1/token",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == 1:
                token = data["result"]["access_token"]
                expires_in = data["result"].get("expires_in", 3600)
                _access_token_cache["token"]      = token
                _access_token_cache["expires_at"] = time_module.time() + expires_in
                return token
            else:
                print(f"[GoPlus] Erreur token: {data.get('message')}")
                return None
    except Exception as e:
        print(f"[GoPlus] Erreur _get_access_token: {e}")
        return None


async def check_token_security(token_address: str) -> dict:
    """
    Endpoint officiel GoPlus Solana :
    GET /api/v1/solana/token_security?contract_addresses={address}

    Auth :
    - Avec APP_KEY + APP_SECRET : génère un access_token via SHA1
    - Sans credentials         : requête libre (30 req/min, sans header auth)

    Docs : https://docs.gopluslabs.io/reference/getaccesstokenusingpost
    """
    url     = f"{GOPLUS_BASE}/api/v1/solana/token_security"
    headers = {}
    params  = {"contract_addresses": token_address}

    # Tente d'obtenir un access_token si les credentials sont fournis
    access_token = await _get_access_token()
    if access_token:
        headers["Authorization"] = access_token
    # Si pas de credentials → on envoie SANS header Authorization
    # (mode gratuit 30 req/min, fonctionne sans auth)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            code = data.get("code")

            if code == 1:
                result     = data.get("result", {})
                token_data = result.get(token_address.lower(),
                             result.get(token_address, {}))
                if not token_data:
                    return _unverified_result("Token absent dans la réponse GoPlus")
                return parse_goplus_result(token_data)

            # Échec API
            message = data.get("message", "erreur inconnue")
            print(f"[GoPlus] Code {code}: {message}")
            return _unverified_result(f"GoPlus API: {message[:60]}")

    except httpx.TimeoutException:
        return _unverified_result("GoPlus timeout")
    except Exception as e:
        print(f"[GoPlus] Erreur: {e}")
        return _unverified_result(str(e)[:60])


def _unverified_result(reason: str) -> dict:
    """
    Retourné quand GoPlus est indisponible.
    Le token ne sera pas éliminé mais signalé avec avertissement.
    """
    return {
        "is_honeypot":         False,
        "is_mintable":         False,
        "is_freezable":        False,
        "top10_holders_ratio": None,
        "creator_percent":     0,
        "is_lp_locked":        True,
        "lp_lock_days":        30,
        "holder_count":        100,
        "total_supply":        "0",
        "buy_tax":             0,
        "sell_tax":            0,
        "cannot_sell_all":     False,
        "error":               None,
        "is_unverified":       True,
        "unverified_reason":   reason,
    }


def parse_goplus_result(data: dict) -> dict:
    """Parse les champs de sécurité retournés par GoPlus pour Solana."""

    def to_float(val, default=0.0):
        try: return float(val)
        except: return default

    def to_int(val, default=0):
        try: return int(val)
        except: return default

    top10 = data.get("top10_holders_ratio") or data.get("top_10_holders_rate")

    creator_pct = to_float(data.get("creator_percent", 0))
    if creator_pct == 0:
        creator_pct = to_float(data.get("deployer_percent", 0))

    lp_locked      = data.get("lp_locked", "0")
    is_lp_locked   = str(lp_locked) in ("1", "true", "True")
    lock_days      = 0
    lp_lock_detail = data.get("lp_lock_detail", [])
    if isinstance(lp_lock_detail, list) and lp_lock_detail:
        now = time_module.time()
        for lock in lp_lock_detail:
            end_time = to_float(lock.get("end_time", 0))
            if end_time > now:
                lock_days = max(lock_days, int((end_time - now) / 86400))

    return {
        "is_honeypot":         data.get("honeypot", "0") == "1",
        "is_mintable":         data.get("mintable", "0") == "1",
        "is_freezable":        data.get("freezable", "0") == "1",
        "top10_holders_ratio": to_float(top10) if top10 is not None else None,
        "creator_percent":     creator_pct,
        "is_lp_locked":        is_lp_locked,
        "lp_lock_days":        lock_days,
        "holder_count":        to_int(data.get("holder_count", 0)),
        "total_supply":        data.get("total_supply", "0"),
        "buy_tax":             to_float(data.get("buy_tax", 0)),
        "sell_tax":            to_float(data.get("sell_tax", 0)),
        "cannot_sell_all":     data.get("cannot_sell_all", "0") == "1",
        "error":               None,
        "is_unverified":       False,
        "unverified_reason":   None,
    }
