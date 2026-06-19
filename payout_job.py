"""
Daily payout job — runs at 00:00 UTC.

For every user with a queued payout and a set LTC address, sends the LTC via
FaucetPay API using the live LTC/USD price fetched from CoinGecko.
"""

from __future__ import annotations

import logging

from telegram import Bot

import database as db
from faucetpay import get_ltc_price_usd, send_ltc_payout

logger = logging.getLogger(__name__)


async def run_daily_payouts(bot: Bot) -> None:
    """Process all pending payouts. Called by APScheduler."""
    logger.info("Starting daily payout job...")

    ltc_price = await get_ltc_price_usd()
    if ltc_price is None:
        logger.error("Cannot run payouts — CoinGecko price fetch failed.")
        return

    logger.info("LTC price: $%.4f", ltc_price)

    pending = db.get_all_pending_payouts()
    if not pending:
        logger.info("No pending payouts today.")
        return

    stats = db.get_stats()

    for uid, amount_usd in pending:
        user = db.get_user(uid)
        if user is None:
            logger.warning("Payout for unknown uid %d — skipping.", uid)
            continue

        ltc_address = user.get("ltc_address")
        if not ltc_address:
            logger.warning("User %d has no LTC address — skipping.", uid)
            await _notify_user(bot, uid, "⚠️ Payout skipped: you have no LTC address set.\nUse /setaddress to add one.")
            continue

        logger.info("Paying uid=%d $%.6f → %s", uid, amount_usd, ltc_address)
        result = await send_ltc_payout(ltc_address, amount_usd, ltc_price)

        if result["success"]:
            db.clear_pending_payout(uid)
            user["withdrawal_queued"] = False
            db.save_user(user)

            stats["total_paid_usd"] = stats.get("total_paid_usd", 0.0) + amount_usd
            db.save_stats(stats)

            ltc_sent = amount_usd / ltc_price
            await _notify_user(
                bot,
                uid,
                f"✅ Payout sent!\n\n"
                f"💰 Amount: ${amount_usd:.6f} ({ltc_sent:.8f} LTC)\n"
                f"📬 Address: <code>{ltc_address}</code>\n"
                f"🔖 ID: {result['payout_id']}\n\n"
                f"Thank you for using our faucet! 🎉",
            )
        else:
            logger.error("Payout failed for uid=%d: %s", uid, result["message"])
            await _notify_user(
                bot,
                uid,
                f"❌ Payout failed: {result['message']}\nWe'll retry tomorrow.",
            )

    logger.info("Daily payout job complete.")


async def _notify_user(bot: Bot, uid: int, text: str) -> None:
    try:
        await bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
    except Exception as exc:
        logger.warning("Could not notify uid=%d: %s", uid, exc)
