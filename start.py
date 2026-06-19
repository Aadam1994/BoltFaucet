"""
/start handler — welcome message and referral registration.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import PAYOUT_HOUR_UTC
from keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    is_new = db.get_user(user.id) is None
    record = db.get_or_create_user(user.id, user.username)

    # Handle referral link: /start ref_<uid>
    if context.args and context.args[0].startswith("ref_") and is_new:
        try:
            referrer_uid = int(context.args[0][4:])
            if referrer_uid != user.id:
                referrer = db.get_user(referrer_uid)
                if referrer:
                    import time as _time
                    record["referrer_uid"] = referrer_uid
                    db.save_user(record)
                    referrer["referral_count"] = referrer.get("referral_count", 0) + 1
                    # Track join timestamp for referral burst detection
                    timestamps = referrer.get("referral_join_timestamps", [])
                    timestamps.append(_time.time())
                    # Keep only the last 200 timestamps to bound memory
                    referrer["referral_join_timestamps"] = timestamps[-200:]
                    db.save_user(referrer)
                    logger.info("User %d referred by %d", user.id, referrer_uid)
        except ValueError:
            pass

    reward = db.get_reward_usd()
    min_withdrawal = db.get_min_withdrawal_usd()
    claims_needed = int(min_withdrawal / reward) if reward > 0 else 0
    text = (
        f"👋 Welcome, <b>{user.first_name}</b>!\n\n"
        f"🚰 <b>LTC Faucet Bot</b>\n\n"
        f"How it works:\n"
        f"1️⃣ Watch <b>2 ads</b>\n"
        f"2️⃣ Solve a quick <b>captcha</b>\n"
        f"3️⃣ Earn <b>${reward:.4f}</b> in LTC per claim\n\n"
        f"💰 Minimum withdrawal: <b>${min_withdrawal:.2f}</b> ({claims_needed} claims)\n"
        f"⏰ Payouts sent daily at <b>{PAYOUT_HOUR_UTC:02d}:00 UTC</b>\n\n"
        f"Use /setaddress to set your LTC wallet address.\n\n"
        f"Let's earn! 👇"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
