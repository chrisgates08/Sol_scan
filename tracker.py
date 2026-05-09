import time
from config import TRACKER

async def check_multiplier(pair_address: str, alert_price: float,
                            alert_time: int,  last_multiplier: float,
                            current_price: float) -> dict:
    """
    Compare le prix actuel au prix d'alerte initial.
    Retourne le type d'événement à notifier (MULTIPLIER,
    TAKE_PROFIT_WARNING, TIMEOUT) ou None.
    """
    if alert_price <= 0 or current_price <= 0:
        return {"event": None}

    now          = time.time()
    hours_since  = (now - alert_time) / 3600
    multiplier   = current_price / alert_price

    # Durée max de suivi atteinte
    if hours_since > TRACKER["max_track_hours"]:
        return {"event": "TIMEOUT", "multiplier": multiplier,
                "hours": hours_since}

    # Vérifie les paliers de gain dans l'ordre croissant
    for target in sorted(TRACKER["multipliers"]):
        if multiplier >= target and last_multiplier < target:
            return {
                "event":      "MULTIPLIER",
                "target":     target,
                "multiplier": multiplier,
                "price":      current_price,
            }

    # Alerte de chute si au moins un palier a été atteint
    if last_multiplier >= TRACKER["multipliers"][0]:
        peak_price     = alert_price * last_multiplier
        drop_from_peak = (peak_price - current_price) / peak_price
        if drop_from_peak >= TRACKER["drop_warning"]:
            return {
                "event":     "TAKE_PROFIT_WARNING",
                "multiplier": multiplier,
                "drop_pct":  drop_from_peak * 100,
                "price":     current_price,
            }

    return {"event": None, "multiplier": multiplier}
