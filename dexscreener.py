import httpx
import time
from typing import Optional

DEXSCREENER_BASE = "https://api.dexscreener.com"

async def get_latest_token_profiles(chain_id: str = "solana") -> list:
    """
    Endpoint officiel DexScreener :
    GET /token-profiles/latest/v1
    Retourne les derniers tokens listés, filtrés par chain.
    """
    url = f"{DEXSCREENER_BASE}/token-profiles/latest/v1"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return [t for t in data if t.get("chainId") == chain_id]
            return []
    except Exception as e:
        print(f"[DexScreener] Erreur get_latest_token_profiles: {e}")
        return []

async def get_token_pairs(chain_id: str, token_address: str) -> list:
    """
    Endpoint officiel DexScreener :
    GET /token-pairs/v1/{chainId}/{tokenAddress}
    Retourne toutes les paires de trading d'un token.
    """
    url = f"{DEXSCREENER_BASE}/token-pairs/v1/{chain_id}/{token_address}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("pairs", [])
    except Exception as e:
        print(f"[DexScreener] Erreur get_token_pairs: {e}")
        return []

async def get_pair_data(chain_id: str, pair_address: str) -> Optional[dict]:
    """
    Endpoint officiel DexScreener :
    GET /latest/dex/pairs/{chainId}/{pairId}
    Utilisé pour le suivi post-alerte (prix en temps réel).
    """
    url = f"{DEXSCREENER_BASE}/latest/dex/pairs/{chain_id}/{pair_address}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            pairs = data.get("pairs", [])
            return pairs[0] if pairs else None
    except Exception as e:
        print(f"[DexScreener] Erreur get_pair_data: {e}")
        return None

def extract_metrics(pair: dict) -> dict:
    """Extrait les métriques clés d'une paire DexScreener."""
    now_ms     = int(time.time() * 1000)
    created_at = pair.get("pairCreatedAt", now_ms)
    age_minutes = (now_ms - created_at) / 60_000

    liquidity = pair.get("liquidity", {})
    volume    = pair.get("volume", {})
    txns      = pair.get("txns", {})

    liq_usd  = liquidity.get("usd", 0) or 0
    vol_1h   = volume.get("h1", 0) or 0
    vol_5m   = volume.get("m5", 0) or 0
    buys_1h  = txns.get("h1", {}).get("buys", 0)  or 0
    sells_1h = txns.get("h1", {}).get("sells", 1) or 1

    return {
        "pair_address":   pair.get("pairAddress", ""),
        "token_name":     pair.get("baseToken", {}).get("name", "Unknown"),
        "symbol":         pair.get("baseToken", {}).get("symbol", "???"),
        "token_address":  pair.get("baseToken", {}).get("address", ""),
        "price_usd":      float(pair.get("priceUsd", 0) or 0),
        "market_cap":     float(pair.get("marketCap", 0) or 0),
        "fdv":            float(pair.get("fdv", 0) or 0),
        "liquidity_usd":  liq_usd,
        "volume_1h":      vol_1h,
        "volume_5m":      vol_5m,
        "txns_1h_buys":   buys_1h,
        "txns_1h_sells":  sells_1h,
        "buy_sell_ratio": buys_1h / sells_1h,
        "vol_liq_ratio":  vol_1h / liq_usd if liq_usd > 0 else 0,
        "age_minutes":    age_minutes,
        "dex_url":        pair.get("url", ""),
        "chain_id":       pair.get("chainId", ""),
        "dex_id":         pair.get("dexId", ""),
    }
