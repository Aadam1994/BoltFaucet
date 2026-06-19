"""
/referrals — leaderboard of top referrers by earnings generated.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import LEADERBOARD_SIZE
from keyboards import back_keyboard

MEDALS = ["🥇", "🥈", "🥉"] + ["🏅"] * 10


async def referrals_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.message
    user = update.effective_user
    if user is None:
        return

    board = db.get_top_referrers(limit=LEADERBOARD_SIZE)

    if not board:
        text = (
            "🤝 <b>Top Referrers</b>\n\n"
            "No referral earnings yet — be the first!\n\n"
            "Share your referral link via 👥 My Referral and earn "
            "<b>15%</b> of every claim your friends make."
        )
    else:
        lines = ["🤝 <b>Top Referrers</b>\n", "<i>Ranked by total referral earnings</i>\n"]
        user_rank = None

        for i, (uid, earned) in enumerate(board):
            medal = MEDALS[i] if i < len(MEDALS) else f"{i + 1}."
            u = db.get_user(uid)
            name = u.get("username", str(uid)) if u else str(uid)
            ref_count = u.get("referral_count", 0) if u else 0
            lines.append(
                f"{medal} <b>{name}</b> — ${earned:.4f} "
                f"<i>({ref_count} referral{'s' if ref_count != 1 else ''})</i>"
            )
            if uid == user.id:
                user_rank = i + 1

        text = "\n".join(lines)

        if user_rank:
            text += f"\n\n🎯 Your rank: <b>#{user_rank}</b>"
        else:
            # Check if user appears outside top N
            full_board = db.get_top_referrers(limit=1000)
            for i, (uid, _) in enumerate(full_board):
                if uid == user.id:
                    text += f"\n\n🎯 Your rank: <b>#{i + 1}</b>"
                    break
            else:
                my_record = db.get_user(user.id)
                my_earned = my_record.get("referral_earnings_generated_usd", 0.0) if my_record else 0.0
                if my_earned == 0:
                    text += "\n\n🎯 You have no referral earnings yet. Start sharing your link!"

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=back_keyboard())
