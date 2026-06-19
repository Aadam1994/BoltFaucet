"""
Claim flow:
  /claim or button → watch ad 1 → watch ad 2 → captcha → reward credited
"""

from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import (
    ADS_PER_CLAIM,
    REFERRAL_BONUS_PERCENT,
)
from keyboards import back_keyboard, captcha_keyboard, watch_ad_keyboard

logger = logging.getLogger(__name__)


async def claim_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point: /claim command or 'claim' callback."""
    query = update.callback_query
    message = update.message

    user = update.effective_user
    if user is None:
        return

    # Check if user is banned
    record_pre = db.get_user(user.id)
    if record_pre and record_pre.get("banned"):
        reason = record_pre.get("ban_reason") or "No reason given"
        text = f"🚫 <b>You are banned</b>\n\nReason: {reason}\n\nContact support if you believe this is a mistake."
        if query:
            await query.answer("You are banned.", show_alert=True)
            await query.edit_message_text(text, parse_mode="HTML")
        else:
            await message.reply_text(text, parse_mode="HTML")
        return

    # Check faucet paused
    if db.is_faucet_paused():
        text = "⏸ The faucet is currently paused. Check back soon!"
        if query:
            await query.answer()
            await query.edit_message_text(text, reply_markup=back_keyboard())
        else:
            await message.reply_text(text, reply_markup=back_keyboard())
        return

    record = db.get_or_create_user(user.id, user.username)

    # Enforce cooldown
    now = time.time()
    last = record.get("last_claim_ts", 0)
    elapsed = now - last
    remaining = db.get_cooldown_seconds() - elapsed

    if remaining > 0:
        text = (
            f"⏳ Cooldown active!\n\n"
            f"Next claim in <b>{remaining:.0f}s</b>."
        )
        if query:
            await query.answer(f"Wait {remaining:.0f}s", show_alert=True)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
        else:
            await message.reply_text(text, parse_mode="HTML", reply_markup=back_keyboard())
        return

    # Reset ad counter for this claim cycle
    record["ads_watched"] = 0
    record["captcha_pending"] = False
    db.save_user(record)

    text = (
        "📺 <b>Step 1 of 3 — Watch Ads</b>\n\n"
        "You need to watch <b>2 ads</b> before claiming your reward.\n"
        "Click the button below to watch Ad 1."
    )
    kb = watch_ad_keyboard(1)

    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def watch_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle watch_ad_<n> callback."""
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None:
        return

    await query.answer("✅ Ad watched!")

    # Parse which ad number was just watched
    ad_number = int(query.data.split("_")[-1])

    record = db.get_or_create_user(user.id, user.username)
    watched = record.get("ads_watched", 0)

    # Guard against replaying the same ad
    if ad_number <= watched:
        await query.edit_message_text(
            "⚠️ You already watched this ad.",
            reply_markup=back_keyboard(),
        )
        return

    watched = ad_number
    record["ads_watched"] = watched
    db.save_user(record)

    if watched < ADS_PER_CLAIM:
        # Show next ad button
        next_ad = watched + 1
        text = (
            f"✅ Ad {watched}/{ADS_PER_CLAIM} watched!\n\n"
            f"Keep going — watch Ad {next_ad} to continue."
        )
        await query.edit_message_text(
            text, parse_mode="HTML", reply_markup=watch_ad_keyboard(next_ad)
        )
    else:
        # All ads watched → show captcha
        record["captcha_pending"] = True
        db.save_user(record)

        question, kb = captcha_keyboard()
        text = (
            f"✅ Both ads watched!\n\n"
            f"🔐 <b>Step 3 — Solve the captcha</b>\n\n"
            f"<b>{question}</b>"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


async def captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle captcha_<answer>_<correct> callback."""
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None:
        return

    parts = query.data.split("_")  # captcha_<answer>_<correct>
    try:
        answer = int(parts[1])
        correct = int(parts[2])
    except (IndexError, ValueError):
        await query.answer("Invalid captcha data", show_alert=True)
        return

    record = db.get_or_create_user(user.id, user.username)

    if not record.get("captcha_pending"):
        await query.answer("Start a new claim first.", show_alert=True)
        return

    if answer != correct:
        await query.answer("❌ Wrong answer! Try again.", show_alert=True)
        # Regenerate captcha
        question, kb = captcha_keyboard()
        await query.edit_message_text(
            f"❌ Wrong! Try again.\n\n🔐 <b>{question}</b>",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    # Correct captcha → credit reward
    await query.answer("✅ Correct!")

    now = time.time()
    reward = db.get_reward_usd()
    record["balance_usd"] = record.get("balance_usd", 0.0) + reward
    record["total_earned_usd"] = record.get("total_earned_usd", 0.0) + reward
    record["claims_count"] = record.get("claims_count", 0) + 1
    record["last_claim_ts"] = now
    record["ads_watched"] = 0
    record["captcha_pending"] = False
    # Keep a rolling window of claim timestamps for spike detection (last 200)
    claim_ts_list = record.get("claim_timestamps", [])
    claim_ts_list.append(now)
    record["claim_timestamps"] = claim_ts_list[-200:]
    db.save_user(record)

    # Update daily leaderboard
    db.add_daily_earnings(user.id, reward)

    # Update global stats
    stats = db.get_stats()
    stats["total_claims"] = stats.get("total_claims", 0) + 1
    db.save_stats(stats)

    # Pay referral bonus
    referrer_uid = record.get("referrer_uid")
    if referrer_uid:
        bonus = reward * REFERRAL_BONUS_PERCENT
        referrer = db.get_user(referrer_uid)
        if referrer:
            referrer["balance_usd"] = referrer.get("balance_usd", 0.0) + bonus
            referrer["total_earned_usd"] = referrer.get("total_earned_usd", 0.0) + bonus
            referrer["referral_earnings_generated_usd"] = (
                referrer.get("referral_earnings_generated_usd", 0.0) + bonus
            )
            db.save_user(referrer)
            db.add_daily_earnings(referrer_uid, bonus)

    # Run abuse checks in background — non-blocking
    import asyncio
    import antiabuse
    asyncio.create_task(antiabuse.run_checks(context.bot, user.id))

    from keyboards import main_menu_keyboard
    text = (
        f"🎉 <b>Claim successful!</b>\n\n"
        f"💰 Earned: <b>${reward:.4f}</b>\n"
        f"💼 Total balance: <b>${record['balance_usd']:.4f}</b>\n"
        f"📊 Claims today: <b>{record['claims_count']}</b>\n\n"
        f"Come back in {db.get_cooldown_seconds()}s for your next claim!"
    )
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
