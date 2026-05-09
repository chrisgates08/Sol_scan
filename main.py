import asyncio
import logging

from telegram import Bot
from telegram.error import TelegramError

from config import (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CHAIN_ID,
                    SCAN_INTERVAL_SECONDS, TRACKER_INTERVAL_SECONDS, FILTERS)
from database import (init_db, is_already_alerted, save_alerted_token,
                      get_tracked_tokens, update_tracking, save_scan_stats)
from dexscreener import (get_latest_token_profiles, get_token_pairs,
                          get_pair_data, extract_metrics)
from goplus import check_token_security
from filters import evaluate_token
from tracker import check_multiplier

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  FORMATTERS TELEGRAM
# ─────────────────────────────────────────────────────────────

def format_signal_message(metrics: dict, security: dict,
                           evaluation: dict) -> str:
    is_strong     = evaluation["signal"] == "STRONG"
    is_unverified = evaluation.get("is_unverified", False)

    if is_strong:
        emoji, label = "🟢", "SIGNAL FORT"
    else:
        emoji, label = "🟡", "SIGNAL MODÉRÉ"

    # Avertissement sécurité si GoPlus indisponible
    security_warning = ""
    if is_unverified:
        reason = security.get("unverified_reason", "GoPlus indisponible")
        security_warning = f"\n⚠️ *Sécurité non vérifiée* — {reason}\n💡 Ajoutez GOPLUS\\_API\\_KEY dans .env\n"

    lines = [
        f"{emoji} *{label}* — `{metrics['symbol']}`",
        f"",
        f"📛 *Nom :* {metrics['token_name']}",
        f"⛓️ *DEX :* {metrics['dex_id'].upper()} | Solana",
        security_warning,
        f"💰 *Prix :* ${metrics['price_usd']:.8f}",
        f"📊 *Market Cap :* ${metrics['market_cap']:,.0f}",
        f"💧 *Liquidité :* ${metrics['liquidity_usd']:,.0f}",
        f"📈 *Volume 1h :* ${metrics['volume_1h']:,.0f}",
        f"📉 *Volume 5m :* ${metrics['volume_5m']:,.0f}",
        f"⏱️ *Âge :* {metrics['age_minutes']:.0f} min",
        f"🔄 *Buy/Sell :* {metrics['buy_sell_ratio']:.2f}",
        f"",
        f"✅ Critères verts : {evaluation['green_count']}",
        f"🟡 Critères jaunes : {evaluation['yellow_count']}",
        f"",
        "📋 *Analyse :*",
    ]
    for d in evaluation["details"][:8]:
        lines.append(f"  {d}")

    lines += [
        f"",
        f"🔗 [Voir sur DexScreener]({metrics['dex_url']})",
        f"",
        f"`{metrics['token_address']}`",
    ]
    return "\n".join(lines)


def format_multiplier_message(token_name: str, symbol: str,
                               event: dict, dex_url: str) -> str:
    e = event
    if e["event"] == "MULTIPLIER":
        emoji = "🚀🚀" if e["target"] >= 3 else "🚀"
        return (
            f"{emoji} *x{e['target']:.0f} ATTEINT !* — `{symbol}`\n\n"
            f"📛 {token_name}\n"
            f"💰 Prix actuel : ${e['price']:.8f}\n"
            f"📊 Multiplicateur réel : *x{e['multiplier']:.2f}*\n\n"
            f"🔗 [Voir sur DexScreener]({dex_url})"
        )
    elif e["event"] == "TAKE_PROFIT_WARNING":
        return (
            f"⚠️ *TAKE PROFIT WARNING* — `{symbol}`\n\n"
            f"📛 {token_name}\n"
            f"📉 Chute de *{e['drop_pct']:.1f}%* depuis le sommet\n"
            f"💰 Prix actuel : ${e['price']:.8f}\n\n"
            f"💡 Considérez à prendre vos bénéfices."
        )
    return ""

# ─────────────────────────────────────────────────────────────
#  RAPPORT DE DÉMARRAGE
# ─────────────────────────────────────────────────────────────

async def send_startup_report(bot: Bot, total_profiles: int,
                               passed_market: int, passed_security: int,
                               signals_sent: int, goplus_active: bool):
    goplus_status = "✅ Active" if goplus_active else "⚠️ Inactive (clé manquante)"
    msg = (
        f"🤖 *Memecoin Bot démarré — Solana*\n\n"
        f"🔍 *Paires scannées :* {total_profiles}\n"
        f"✅ *Passent les filtres marché :* {passed_market}\n"
        f"🛡️ *Validées après filtres :* {passed_security}\n"
        f"🚨 *Signaux émis au démarrage :* {signals_sent}\n\n"
        f"🔐 *GoPlus Security :* {goplus_status}\n"
        f"⏱️ Prochain scan dans {SCAN_INTERVAL_SECONDS}s\n"
        f"📡 Suivi des tokens toutes les {TRACKER_INTERVAL_SECONDS}s"
    )
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=msg,
        parse_mode="Markdown",
    )

# ─────────────────────────────────────────────────────────────
#  SCAN PRINCIPAL
# ─────────────────────────────────────────────────────────────

async def run_scan(bot: Bot, is_startup: bool = False):
    log.info("🔍 Démarrage du scan DexScreener...")

    profiles = await get_latest_token_profiles(CHAIN_ID)
    log.info(f"   {len(profiles)} profils Solana récupérés")

    passed_market   = 0
    passed_security = 0
    signals_sent    = 0
    goplus_active   = False
    f               = FILTERS

    for profile in profiles:
        token_address = profile.get("tokenAddress")
        if not token_address:
            continue

        pairs = await get_token_pairs(CHAIN_ID, token_address)
        if not pairs:
            continue

        # Paire avec la liquidité la plus haute
        best_pair = max(
            pairs,
            key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0
        )
        metrics = extract_metrics(best_pair)

        if await is_already_alerted(metrics["pair_address"]):
            continue

        # Pré-filtre rapide avant d'appeler GoPlus
        liq  = metrics["liquidity_usd"]
        mcap = metrics["market_cap"]
        age  = metrics["age_minutes"]

        if (liq  < f["liquidity_min"] or liq  > f["liquidity_max"]
         or mcap < f["mcap_min"]      or mcap > f["mcap_max"]
         or age  < f["age_min_minutes"] or age > f["age_max_minutes"]
         or metrics["volume_1h"] < f["volume_1h_min"]):
            continue

        passed_market += 1
        await asyncio.sleep(0.5)

        security = await check_token_security(token_address)

        # Vérifie si GoPlus répond correctement
        if not security.get("is_unverified", False):
            goplus_active = True

        evaluation = evaluate_token(metrics, security)

        if not evaluation["passed"]:
            if evaluation["red_flags"]:
                log.info(f"   ❌ {metrics['symbol']} — {evaluation['red_flags'][0]}")
            continue

        passed_security += 1

        try:
            msg = format_signal_message(metrics, security, evaluation)
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            await save_alerted_token(
                pair_address = metrics["pair_address"],
                token_name   = metrics["token_name"],
                symbol       = metrics["symbol"],
                alert_price  = metrics["price_usd"],
                market_cap   = metrics["market_cap"],
                liquidity    = metrics["liquidity_usd"],
                score        = evaluation["signal"],
            )
            signals_sent += 1
            unverified_tag = " [⚠️ sécurité non vérifiée]" if evaluation.get("is_unverified") else ""
            log.info(f"   ✅ Signal : {metrics['symbol']} ({evaluation['signal']}){unverified_tag} "
                     f"— MC: ${metrics['market_cap']:,.0f}")
        except TelegramError as e:
            log.error(f"   Telegram erreur: {e}")

        await asyncio.sleep(0.5)

    await save_scan_stats(len(profiles), passed_market,
                          passed_security, signals_sent)

    if is_startup:
        await send_startup_report(bot, len(profiles), passed_market,
                                   passed_security, signals_sent, goplus_active)

    log.info(f"✅ Scan terminé — {signals_sent} signal(s) | "
             f"{passed_market} marché | {passed_security} sécurité | "
             f"GoPlus: {'✅' if goplus_active else '⚠️'}")

# ─────────────────────────────────────────────────────────────
#  TRACKER POST-ALERTE
# ─────────────────────────────────────────────────────────────

async def run_tracker(bot: Bot):
    tracked = await get_tracked_tokens()
    if not tracked:
        return

    log.info(f"📡 Suivi de {len(tracked)} token(s)...")

    for row in tracked:
        pair_address, name, symbol, alert_price, alert_time, last_mult = row

        pair_data = await get_pair_data(CHAIN_ID, pair_address)
        if not pair_data:
            continue

        metrics       = extract_metrics(pair_data)
        current_price = metrics["price_usd"]

        event = await check_multiplier(
            pair_address    = pair_address,
            alert_price     = alert_price,
            alert_time      = alert_time,
            last_multiplier = last_mult or 0,
            current_price   = current_price,
        )

        if event["event"] == "TIMEOUT":
            await update_tracking(pair_address, tracking=0)
            log.info(f"   ⏹️ {symbol} sorti du suivi (48h écoulées)")

        elif event["event"] == "MULTIPLIER":
            msg = format_multiplier_message(name, symbol, event, metrics["dex_url"])
            try:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                await update_tracking(pair_address,
                                      last_multiplier=event["target"])
                log.info(f"   🚀 {symbol} x{event['target']:.0f} atteint!")
            except TelegramError as e:
                log.error(f"   Telegram erreur tracker: {e}")

        elif event["event"] == "TAKE_PROFIT_WARNING":
            msg = format_multiplier_message(name, symbol, event, metrics["dex_url"])
            try:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                await update_tracking(pair_address, tracking=0)
            except TelegramError as e:
                log.error(f"   Telegram erreur tracker: {e}")

        await asyncio.sleep(1)

# ─────────────────────────────────────────────────────────────
#  BOUCLE PRINCIPALE
# ─────────────────────────────────────────────────────────────

async def main():
    log.info("🚀 Démarrage du Memecoin Bot Solana...")
    await init_db()

    bot             = Bot(token=TELEGRAM_BOT_TOKEN)
    tracker_counter = 0

    await run_scan(bot, is_startup=True)

    while True:
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)
        tracker_counter += SCAN_INTERVAL_SECONDS

        await run_scan(bot, is_startup=False)

        if tracker_counter >= TRACKER_INTERVAL_SECONDS:
            await run_tracker(bot)
            tracker_counter = 0

if __name__ == "__main__":
    asyncio.run(main())
