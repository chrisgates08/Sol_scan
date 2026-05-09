import os
from dotenv import load_dotenv
load_dotenv()

# ── Telegram ──────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── GoPlus Security ────────────────────────────────
# Optionnel — sans ces variables, le bot utilise le mode
# gratuit (30 req/min, sans authentification).
# Pour obtenir app_key + app_secret :
# https://platform.gopluslabs.io → Create Application
GOPLUS_APP_KEY    = os.getenv("GOPLUS_APP_KEY", "")
GOPLUS_APP_SECRET = os.getenv("GOPLUS_APP_SECRET", "")

# ── Chaîne cible ───────────────────────────────────
CHAIN_ID = "solana"

# ── Intervalles de scan ────────────────────────────
SCAN_INTERVAL_SECONDS    = 60
TRACKER_INTERVAL_SECONDS = 120

# ── Seuils de filtrage ─────────────────────────────
FILTERS = {
    "age_min_minutes":    20,
    "age_max_minutes":    360,
    "age_strong_min":     30,
    "age_strong_max":     180,

    "liquidity_min":        15_000,
    "liquidity_strong_min": 20_000,
    "liquidity_strong_max": 150_000,
    "liquidity_max":        500_000,

    "mcap_min":        30_000,
    "mcap_strong_max": 700_000,
    "mcap_max":      1_500_000,

    "volume_1h_min": 5_000,
    "volume_5m_min": 500,

    "vol_liq_ratio_moderate": 0.3,
    "vol_liq_ratio_strong":   0.6,

    "txns_1h_min":       30,
    "holders_moderate":  75,
    "holders_strong":   150,

    "buy_sell_ratio_min":    1.0,
    "buy_sell_ratio_strong": 1.5,
}

# ── Sécurité GoPlus ────────────────────────────────
SECURITY = {
    "top10_holders_max":       0.25,
    "dev_wallet_max":          0.10,
    "min_liquidity_lock_days": 30,
}

# ── Suivi post-alerte ──────────────────────────────
TRACKER = {
    "multipliers":     [2.0, 3.0, 5.0],
    "drop_warning":    0.30,
    "max_track_hours": 48,
}

MIN_GREEN_CRITERIA = 5
