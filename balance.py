"""
/balance handler.
"""

from __future__ import annotations

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import PAYOUT_HOUR_UTC
from keyboards import back_keyboard


def _next_payout_str() -> str:
    now = datetime.now(timezone.utc)
    if now.hour < PAYOUT_HOUR_UTC or (now.hour == PAYOUT_HOUR_UTC and now.minute == 0):
        label = "Today"
    else:
        label = "Tomorrow"
    return f"{label} {PAYOUT_HOUR_UTC:02d}:00 UTC"


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.message
    user = update.effective_user
    if user is None:
        return

    record = db.get_or_create_user(user.id, user.username)
    bal = record.get("balance_usd", 0.0)
    total = record.get("total_earned_usd", 0.0)
    claims = record.get("claims_count", 0)
    queued = db.get_pending_payout(user.id)
    address = record.get("ltc_address") or "Not set"
    min_withdrawal = db.get_min_withdrawal_usd()
    shortfall = max(0.0, min_withdrawal - bal)

    text = (
        f"💼 <b>Your Balance</b>\n\n"
        f"💰 Available: <b>${bal:.6f}</b>\n"
        f"📊 Total earned: <b>${total:.6f}</b>\n"
        f"🔢 Claims made: <b>{claims}</b>\n"
        f"⏳ Queued for payout: <b>${queued:.6f}</b>\n\n"
        f"📬 LTC Address: <code>{address}</code>\n\n"
    )

    if bal >= min_withdrawal:
        text += f"✅ You can withdraw! Use /withdraw\n\n"
    else:
        text += (
            f"⚠️ Need <b>${shortfall:.6f}</b> more to withdraw "
            f"(min ${min_withdrawal:.2f})\n\n"
        )

    text += (
        f"⏰ <b>Next payout: {_next_payout_str()}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📢 <i>Ad slot — check our sponsors!</i>"
    )

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=back_keyboard())
