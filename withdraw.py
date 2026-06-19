"""
/withdraw handler.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import PAYOUT_HOUR_UTC
from keyboards import back_keyboard, set_address_keyboard


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.message
    user = update.effective_user
    if user is None:
        return

    record = db.get_or_create_user(user.id, user.username)
    bal = record.get("balance_usd", 0.0)
    address = record.get("ltc_address")

    async def reply(text: str, kb=None):
        kb = kb or back_keyboard()
        if query:
            await query.answer()
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await message.reply_text(text, parse_mode="HTML", reply_markup=kb)

    if not address:
        await reply(
            "❌ <b>No LTC address set!</b>\n\n"
            "Set your LTC address first to receive payouts.",
            set_address_keyboard(),
        )
        return

    min_withdrawal = db.get_min_withdrawal_usd()
    if bal < min_withdrawal:
        shortfall = min_withdrawal - bal
        await reply(
            f"❌ <b>Balance too low</b>\n\n"
            f"You need <b>${shortfall:.6f}</b> more before withdrawing.\n"
            f"Minimum: ${min_withdrawal:.2f}",
        )
        return

    if record.get("withdrawal_queued"):
        queued = db.get_pending_payout(user.id)
        await reply(
            f"⏳ <b>Withdrawal already queued!</b>\n\n"
            f"Amount: <b>${queued:.6f}</b>\n"
            f"Sending at <b>{PAYOUT_HOUR_UTC:02d}:00 UTC</b> today.",
        )
        return

    # Queue the payout
    db.queue_payout(user.id, bal)
    record["balance_usd"] = 0.0
    record["withdrawal_queued"] = True
    db.save_user(record)

    await reply(
        f"✅ <b>Withdrawal queued!</b>\n\n"
        f"💰 Amount: <b>${bal:.6f}</b>\n"
        f"📬 To: <code>{address}</code>\n"
        f"⏰ Sending at <b>{PAYOUT_HOUR_UTC:02d}:00 UTC</b>\n\n"
        f"You'll receive a confirmation message when the payout is sent.",
    )
