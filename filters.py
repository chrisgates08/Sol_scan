from config import FILTERS, SECURITY, MIN_GREEN_CRITERIA

def evaluate_token(metrics: dict, security: dict) -> dict:
    """
    Évalue un token selon tous les critères définis.
    Si GoPlus est indisponible (is_unverified=True), le signal
    est envoyé avec un avertissement plutôt qu'éliminé.
    """
    f = FILTERS
    s = SECURITY

    red_flags    = []
    green_count  = 0
    yellow_count = 0
    details      = []
    is_unverified = security.get("is_unverified", False)

    # ── SÉCURITÉ GOPLUS ───────────────────────────────────
    if is_unverified:
        # Sécurité non vérifiable → on signale mais on n'élimine pas
        yellow_count += 1
        reason = security.get("unverified_reason", "GoPlus indisponible")
        details.append(f"⚠️ Sécurité non vérifiée : {reason}")
    else:
        if security.get("is_honeypot"):
            red_flags.append("🚫 HONEYPOT détecté")
        if security.get("is_mintable"):
            red_flags.append("🚫 Mint authority active")
        if security.get("is_freezable"):
            red_flags.append("🚫 Freeze authority active")
        if security.get("cannot_sell_all"):
            red_flags.append("🚫 Impossible de tout vendre")
        if security.get("buy_tax", 0) > 10:
            red_flags.append(f"🚫 Buy tax élevée: {security['buy_tax']}%")
        if security.get("sell_tax", 0) > 10:
            red_flags.append(f"🚫 Sell tax élevée: {security['sell_tax']}%")

        top10 = security.get("top10_holders_ratio")
        if top10 is not None:
            if top10 > 0.30:
                red_flags.append(f"🚫 Top10 holders: {top10*100:.1f}% (>30%)")
            elif top10 > s["top10_holders_max"]:
                yellow_count += 1
                details.append(f"🟡 Top10 holders: {top10*100:.1f}%")
            else:
                green_count += 1
                details.append(f"✅ Top10 holders: {top10*100:.1f}%")

        creator_pct = security.get("creator_percent", 0)
        if creator_pct > s["dev_wallet_max"]:
            yellow_count += 1
            details.append(f"🟡 Dev wallet: {creator_pct*100:.1f}%")
        else:
            green_count += 1
            details.append(f"✅ Dev wallet: {creator_pct*100:.1f}%")

        if not security.get("is_lp_locked"):
            red_flags.append("🚫 Liquidité non verrouillée")
        elif security.get("lp_lock_days", 0) < s["min_liquidity_lock_days"]:
            yellow_count += 1
            details.append(f"🟡 LP lock: {security['lp_lock_days']} jours")
        else:
            green_count += 1
            details.append(f"✅ LP lock: {security['lp_lock_days']} jours")

        holders = security.get("holder_count", 0)
        if holders >= f["holders_strong"]:
            green_count += 1
            details.append(f"✅ Holders: {holders}")
        elif holders >= f["holders_moderate"]:
            yellow_count += 1
            details.append(f"🟡 Holders: {holders}")
        else:
            red_flags.append(f"🚫 Holders insuffisants: {holders}")

    # ── ÂGE ───────────────────────────────────────────────
    age = metrics["age_minutes"]
    if age < f["age_min_minutes"] or age > f["age_max_minutes"]:
        red_flags.append(f"🚫 Âge hors plage: {age:.0f} min")
    elif f["age_strong_min"] <= age <= f["age_strong_max"]:
        green_count += 1
        details.append(f"✅ Âge: {age:.0f} min (zone forte)")
    else:
        yellow_count += 1
        details.append(f"🟡 Âge: {age:.0f} min")

    # ── LIQUIDITÉ ─────────────────────────────────────────
    liq = metrics["liquidity_usd"]
    if liq < f["liquidity_min"]:
        red_flags.append(f"🚫 Liquidité trop basse: ${liq:,.0f}")
    elif liq > f["liquidity_max"]:
        red_flags.append(f"🚫 Liquidité trop haute: ${liq:,.0f}")
    elif f["liquidity_strong_min"] <= liq <= f["liquidity_strong_max"]:
        green_count += 1
        details.append(f"✅ Liquidité: ${liq:,.0f}")
    else:
        yellow_count += 1
        details.append(f"🟡 Liquidité: ${liq:,.0f}")

    # ── MARKET CAP ────────────────────────────────────────
    mcap = metrics["market_cap"]
    if mcap < f["mcap_min"]:
        red_flags.append(f"🚫 Market cap trop basse: ${mcap:,.0f}")
    elif mcap > f["mcap_max"]:
        red_flags.append(f"🚫 Market cap trop haute: ${mcap:,.0f}")
    elif mcap <= f["mcap_strong_max"]:
        green_count += 1
        details.append(f"✅ Market cap: ${mcap:,.0f}")
    else:
        yellow_count += 1
        details.append(f"🟡 Market cap: ${mcap:,.0f}")

    # ── VOLUME ────────────────────────────────────────────
    vol_1h = metrics["volume_1h"]
    vol_5m = metrics["volume_5m"]

    if vol_1h < f["volume_1h_min"]:
        red_flags.append(f"🚫 Volume 1h trop bas: ${vol_1h:,.0f}")
    else:
        green_count += 1
        details.append(f"✅ Volume 1h: ${vol_1h:,.0f}")

    if vol_5m >= f["volume_5m_min"]:
        green_count += 1
        details.append(f"✅ Volume 5m: ${vol_5m:,.0f}")
    else:
        yellow_count += 1
        details.append(f"🟡 Volume 5m: ${vol_5m:,.0f}")

    # ── RATIO VOL/LIQ ─────────────────────────────────────
    vlr = metrics["vol_liq_ratio"]
    if vlr >= f["vol_liq_ratio_strong"]:
        green_count += 1
        details.append(f"✅ Vol/Liq ratio: {vlr:.2f}")
    elif vlr >= f["vol_liq_ratio_moderate"]:
        yellow_count += 1
        details.append(f"🟡 Vol/Liq ratio: {vlr:.2f}")
    else:
        red_flags.append(f"🚫 Vol/Liq ratio trop bas: {vlr:.2f}")

    # ── TRANSACTIONS ──────────────────────────────────────
    txns = metrics["txns_1h_buys"] + metrics["txns_1h_sells"]
    if txns < f["txns_1h_min"]:
        red_flags.append(f"🚫 Transactions 1h insuffisantes: {txns}")
    else:
        green_count += 1
        details.append(f"✅ Transactions 1h: {txns}")

    # ── BUY/SELL RATIO ────────────────────────────────────
    bsr = metrics["buy_sell_ratio"]
    if bsr < f["buy_sell_ratio_min"]:
        red_flags.append(f"🚫 Buy/Sell ratio faible: {bsr:.2f}")
    elif bsr >= f["buy_sell_ratio_strong"]:
        green_count += 1
        details.append(f"✅ Buy/Sell ratio: {bsr:.2f}")
    else:
        yellow_count += 1
        details.append(f"🟡 Buy/Sell ratio: {bsr:.2f}")

    # ── DÉCISION FINALE ───────────────────────────────────
    if red_flags:
        signal = "RED"
    elif green_count >= MIN_GREEN_CRITERIA + 2:
        signal = "STRONG" if not is_unverified else "MODERATE"
    elif green_count >= MIN_GREEN_CRITERIA:
        signal = "MODERATE"
    else:
        signal = "WEAK"

    return {
        "signal":        signal,
        "green_count":   green_count,
        "yellow_count":  yellow_count,
        "red_flags":     red_flags,
        "details":       details,
        "passed":        signal in ("STRONG", "MODERATE"),
        "is_unverified": is_unverified,
    }
