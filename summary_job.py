"""
Daily summary job — runs every morning at SUMMARY_HOUR_UTC.

Sends a concise digest to every configured admin covering:
  - New users registered today
  - Total claims made today
  - Earnings generated today (direct + referral)
  - Pending payouts queued for tonight
  - Faucet status
"""

from __future__ import annotations

import logging
import time
from datetime import date, timezone

from telegram import Bot

import database as db
from config import ADMIN_IDS, PAYOUT_HOUR_UTC

logger = logging.getLogger(__name__)


async def run_daily_summary(bot: Bot) -> None:
    """Compile and send the daily summary to all admins."""
    if not ADMIN_IDS:
        logger.info("Daily summary skipped — no ADMIN_IDS configured.")
        return

    logger.info("Sending daily summary to %d admin(s)...", len(ADMIN_IDS))

    today = date.today(timezone.utc).isoformat()
    now_ts = time.time()
    day_start_ts = now_ts - (now_ts % 86400)  # midnight UTC

    # Scan all users to compute today's stats
    new_users_today = 0
    total_claims_today = 0
    earnings_today = 0.0

    for key in db._db_keys_with_prefix("user:"):
        u = db.get_user_by_key(key)
        if u is None:
            continue
        if u.get("registered_at", 0) >= day_start_ts:
            new_users_today += 1

    # Daily leaderboard already tracks per-user earnings today
    board = db.get_daily_leaderboard()
    earnings_today = sum(amt for _, amt in board)
    # Approximate claims today from leaderboard size (each entry = at least 1 claim)
    # Use global stats delta isn't tracked per-day, so use leaderboard entries as proxy
    total_claims_today = len(board)

    # Pending payouts
    pending = db.get_all_pending_payouts()
    pending_usd = sum(amt for _, amt in pending)

    # Global stats
    stats = db.get_stats()
    total_users = stats.get("total_users", 0)
    total_claims_all = stats.get("total_claims", 0)
    total_paid_all = stats.get("total_paid_usd", 0.0)

    paused = "⏸ PAUSED" if db.is_faucet_paused() else "▶️ Running"

    text = (
        f"📋 <b>Daily Summary — {today}</b>\n\n"

        f"<b>Today</b>\n"
        f"👤 New users: <b>{new_users_today}</b>\n"
        f"🔢 Active claimers: <b>{total_claims_today}</b>\n"
        f"💰 Earnings generated: <b>${earnings_today:.4f}</b>\n\n"

        f"<b>Payouts</b>\n"
        f"⏳ Queued for tonight: <b>{len(pending)}</b> users, "
        f"<b>${pending_usd:.6f}</b>\n"
        f"⏰ Sends at {PAYOUT_HOUR_UTC:02d}:00 UTC\n\n"

        f"<b>All-time</b>\n"
        f"👥 Total users: <b>{total_users}</b>\n"
        f"🔢 Total claims: <b>{total_claims_all}</b>\n"
        f"💸 Total paid: <b>${total_paid_all:.6f}</b>\n\n"

        f"🎛 Faucet: {paused}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.error("Failed to send summary to admin %d: %s", admin_id, exc)

    logger.info("Daily summary sent.")
