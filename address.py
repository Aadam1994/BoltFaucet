"""
LTC address management: /setaddress
"""

from __future__ import annotations

import re

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

import database as db
from keyboards import back_keyboard, main_menu_keyboard

WAITING_FOR_ADDRESS = 1

# Basic LTC address regex (legacy L-addresses and M-addresses, plus bech32 ltc1...)
LTC_ADDRESS_RE = re.compile(r"^[LM3][a-km-zA-HJ-NP-Z1-9]{25,34}$|^ltc1[a-z0-9]{39,59}$")


async def setaddress_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    message = update.message

    text = (
        "📝 <b>Set your LTC address</b>\n\n"
        "Send your Litecoin wallet address below.\n\n"
        "Accepted formats:\n"
        "• Legacy: starts with <b>L</b> or <b>M</b>\n"
        "• Bech32: starts with <b>ltc1</b>\n\n"
        "Type /cancel to abort."
    )

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    else:
        await message.reply_text(text, parse_mode="HTML")

    return WAITING_FOR_ADDRESS


async def receive_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    address = (update.message.text or "").strip()

    if not LTC_ADDRESS_RE.match(address):
        await update.message.reply_text(
            "❌ That doesn't look like a valid LTC address. Please try again or /cancel."
        )
        return WAITING_FOR_ADDRESS

    record = db.get_or_create_user(user.id, user.username)
    record["ltc_address"] = address
    db.save_user(record)

    await update.message.reply_text(
        f"✅ <b>LTC address saved!</b>\n\n"
        f"<code>{address}</code>\n\n"
        f"You're all set to receive payouts.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


def build_address_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("setaddress", setaddress_start),
            # Also triggered from inline button
        ],
        states={
            WAITING_FOR_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_address),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
