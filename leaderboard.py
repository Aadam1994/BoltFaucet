"""
/top — daily leaderboard.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import LEADERBOARD_SIZE
from keyboards import back_keyboard

MEDALS = ["🥇", "🥈", "🥉"] + ["🏅"] * 10


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.message
    user = update.effective_user
    if user is None:
        return

    board = db.get_daily_leaderboard()[:LEADERBOARD_SIZE]

    if not board:
        text = "🏆 <b>Today's Leaderboard</b>\n\nNo claims yet today. Be the first!"
    else:
        lines = ["🏆 <b>Today's Top Earners</b>\n"]
        user_rank = None
        for i, (uid, amount) in enumerate(board):
            medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
            u = db.get_user(uid)
            name = u.get("username", str(uid)) if u else str(uid)
            lines.append(f"{medal} <b>{name}</b> — ${amount:.4f}")
            if uid == user.id:
                user_rank = i + 1

        text = "\n".join(lines)
        if user_rank:
            text += f"\n\n🎯 Your rank: <b>#{user_rank}</b>"
        else:
            # Check if user has any earnings today
            full_board = db.get_daily_leaderboard()
            for i, (uid, _) in enumerate(full_board):
                if uid == user.id:
                    text += f"\n\n🎯 Your rank: <b>#{i+1}</b>"
                    break
            else:
                text += "\n\n🎯 You haven't claimed today yet!"

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=back_keyboard())
