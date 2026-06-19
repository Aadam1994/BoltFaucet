"""
Referral link handler.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import REFERRAL_BONUS_PERCENT
from keyboards import back_keyboard


async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.message
    user = update.effective_user
    if user is None:
        return

    record = db.get_or_create_user(user.id, user.username)
    ref_count = record.get("referral_count", 0)

    # Build the bot's referral link
    bot = context.bot
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"

    bonus_pct = int(REFERRAL_BONUS_PERCENT * 100)

    text = (
        f"👥 <b>Your Referral Program</b>\n\n"
        f"Share your link and earn <b>{bonus_pct}%</b> of every claim your referrals make!\n\n"
        f"🔗 Your link:\n<code>{ref_link}</code>\n\n"
        f"📊 Referrals: <b>{ref_count}</b>\n\n"
        f"<i>Tap the link to copy it, then share with friends!</i>"
    )

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=back_keyboard())
