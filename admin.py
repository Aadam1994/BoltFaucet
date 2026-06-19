"""
Admin commands: /stats, /pause, /resume, /setadmin, /broadcast
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database as db
from config import ADMIN_IDS

BROADCAST_WAITING = 1

logger = logging.getLogger(__name__)


def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    s = db.get_stats()
    pending = db.get_all_pending_payouts()
    total_pending_usd = sum(amt for _, amt in pending)
    paused = "⏸ PAUSED" if db.is_faucet_paused() else "▶️ Running"

    text = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"Status: {paused}\n"
        f"👥 Total users: <b>{s.get('total_users', 0)}</b>\n"
        f"🔢 Total claims: <b>{s.get('total_claims', 0)}</b>\n"
        f"💸 Total paid: <b>${s.get('total_paid_usd', 0.0):.6f}</b>\n"
        f"⏳ Pending payouts: <b>{len(pending)}</b> users, "
        f"<b>${total_pending_usd:.6f}</b> total"
    )

    await update.message.reply_text(text, parse_mode="HTML")


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    db.set_faucet_paused(True)
    logger.info("Faucet paused by admin %d", user.id)
    await update.message.reply_text("⏸ Faucet <b>paused</b>.", parse_mode="HTML")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    db.set_faucet_paused(False)
    logger.info("Faucet resumed by admin %d", user.id)
    await update.message.reply_text("▶️ Faucet <b>resumed</b>.", parse_mode="HTML")


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /broadcast — prompts admin for message text."""
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📢 <b>Broadcast Message</b>\n\n"
        "Send the message you want to broadcast to all users.\n"
        "It will be sent exactly as you type it, with HTML formatting supported.\n\n"
        "Type /cancel to abort.",
        parse_mode="HTML",
    )
    return BROADCAST_WAITING


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive the message and send it to all registered users."""
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        return ConversationHandler.END

    message_text = update.message.text or update.message.caption or ""
    if not message_text.strip():
        await update.message.reply_text("❌ Empty message. Try again or /cancel.")
        return BROADCAST_WAITING

    user_ids = db.get_all_user_ids()
    total = len(user_ids)

    if total == 0:
        await update.message.reply_text("⚠️ No registered users yet.")
        return ConversationHandler.END

    status_msg = await update.message.reply_text(
        f"📤 Sending to {total} users…",
        parse_mode="HTML",
    )

    sent = 0
    failed = 0

    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=message_text,
                parse_mode="HTML",
            )
            sent += 1
        except Exception as exc:
            logger.warning("Broadcast failed for uid=%d: %s", uid, exc)
            failed += 1
        # Small delay to avoid hitting Telegram rate limits (30 msg/sec global)
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Broadcast complete!</b>\n\n"
        f"📨 Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>\n"
        f"👥 Total users: <b>{total}</b>",
        parse_mode="HTML",
    )
    logger.info("Broadcast by admin %d — sent %d, failed %d", user.id, sent, failed)
    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END


async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /addbalance <uid> <amount_usd> — credit a user's balance manually.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: <code>/addbalance &lt;user_id&gt; &lt;amount_usd&gt;</code>\n"
            "Example: <code>/addbalance 123456789 0.05</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_uid = int(context.args[0])
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid arguments. UID must be an integer, amount must be a number.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be greater than zero.")
        return

    target = db.get_user(target_uid)
    if target is None:
        await update.message.reply_text(f"❌ No user found with ID <code>{target_uid}</code>.", parse_mode="HTML")
        return

    target["balance_usd"] = target.get("balance_usd", 0.0) + amount
    target["total_earned_usd"] = target.get("total_earned_usd", 0.0) + amount
    db.save_user(target)

    username = target.get("username", str(target_uid))
    new_balance = target["balance_usd"]

    logger.info("Admin %d credited $%.6f to uid=%d", user.id, amount, target_uid)

    await update.message.reply_text(
        f"✅ <b>Balance updated!</b>\n\n"
        f"👤 User: <b>{username}</b> (<code>{target_uid}</code>)\n"
        f"➕ Added: <b>${amount:.6f}</b>\n"
        f"💰 New balance: <b>${new_balance:.6f}</b>",
        parse_mode="HTML",
    )

    # Notify the user
    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text=(
                f"🎁 <b>Balance credited!</b>\n\n"
                f"An admin has added <b>${amount:.6f}</b> to your balance.\n"
                f"💰 New balance: <b>${new_balance:.6f}</b>"
            ),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning("Could not notify uid=%d of balance credit: %s", target_uid, exc)


async def removebalance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /removebalance <uid> <amount_usd> — deduct from a user's balance.
    Use 'all' as amount to wipe the balance entirely.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: <code>/removebalance &lt;user_id&gt; &lt;amount_usd|all&gt;</code>\n"
            "Example: <code>/removebalance 123456789 0.05</code>\n"
            "Example: <code>/removebalance 123456789 all</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID — must be an integer.")
        return

    target = db.get_user(target_uid)
    if target is None:
        await update.message.reply_text(
            f"❌ No user found with ID <code>{target_uid}</code>.", parse_mode="HTML"
        )
        return

    current = target.get("balance_usd", 0.0)
    raw_amount = context.args[1].lower()

    if raw_amount == "all":
        amount = current
    else:
        try:
            amount = float(raw_amount)
        except ValueError:
            await update.message.reply_text("❌ Amount must be a number or 'all'.")
            return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be greater than zero.")
        return

    deducted = min(amount, current)  # never go below zero
    target["balance_usd"] = max(0.0, current - amount)
    db.save_user(target)

    username = target.get("username", str(target_uid))
    new_balance = target["balance_usd"]

    logger.info("Admin %d removed $%.6f from uid=%d", user.id, deducted, target_uid)

    await update.message.reply_text(
        f"✅ <b>Balance updated!</b>\n\n"
        f"👤 User: <b>{username}</b> (<code>{target_uid}</code>)\n"
        f"➖ Removed: <b>${deducted:.6f}</b>\n"
        f"💰 New balance: <b>${new_balance:.6f}</b>",
        parse_mode="HTML",
    )

    # Notify the user only if something was actually deducted
    if deducted > 0:
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text=(
                    f"⚠️ <b>Balance adjusted</b>\n\n"
                    f"An admin has removed <b>${deducted:.6f}</b> from your balance.\n"
                    f"💰 New balance: <b>${new_balance:.6f}</b>"
                ),
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Could not notify uid=%d of balance removal: %s", target_uid, exc)


_start_time: float = __import__("time").time()


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /ping — health check: confirms the bot is alive and shows uptime.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    import time
    from datetime import timedelta

    elapsed = time.time() - _start_time
    uptime = timedelta(seconds=int(elapsed))
    hours, remainder = divmod(int(elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        uptime_str = f"{hours}h {minutes}m {seconds}s"
    elif minutes:
        uptime_str = f"{minutes}m {seconds}s"
    else:
        uptime_str = f"{seconds}s"

    paused = "⏸ Paused" if db.is_faucet_paused() else "▶️ Running"
    stats = db.get_stats()
    pending = db.get_all_pending_payouts()

    await update.message.reply_text(
        f"🏓 <b>Pong!</b>\n\n"
        f"✅ Bot is alive and responding\n"
        f"⏱ Uptime: <b>{uptime_str}</b>\n"
        f"🎛 Faucet: {paused}\n\n"
        f"👥 Users: <b>{stats.get('total_users', 0)}</b>\n"
        f"🔢 Claims: <b>{stats.get('total_claims', 0)}</b>\n"
        f"⏳ Pending payouts: <b>{len(pending)}</b>",
        parse_mode="HTML",
    )


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /schedule — show when the next payout and summary jobs will fire.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    import time
    from datetime import datetime, timezone

    from config import PAYOUT_HOUR_UTC, PAYOUT_MINUTE_UTC, SUMMARY_HOUR_UTC, SUMMARY_MINUTE_UTC

    def next_fire_ts(hour: int, minute: int) -> float:
        now = datetime.now(timezone.utc)
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            from datetime import timedelta
            candidate += timedelta(days=1)
        return candidate.timestamp()

    def fmt_countdown(ts: float) -> str:
        remaining = int(ts - time.time())
        if remaining < 0:
            return "imminent"
        hours, rem = divmod(remaining, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            return f"{hours}h {minutes}m"
        elif minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def fmt_time(hour: int, minute: int) -> str:
        return f"{hour:02d}:{minute:02d} UTC"

    payout_ts = next_fire_ts(PAYOUT_HOUR_UTC, PAYOUT_MINUTE_UTC)
    summary_ts = next_fire_ts(SUMMARY_HOUR_UTC, SUMMARY_MINUTE_UTC)

    payout_dt = datetime.fromtimestamp(payout_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary_dt = datetime.fromtimestamp(summary_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    await update.message.reply_text(
        f"🗓 <b>Scheduled Jobs</b>\n\n"
        f"💸 <b>Daily Payout</b>\n"
        f"   Every day at {fmt_time(PAYOUT_HOUR_UTC, PAYOUT_MINUTE_UTC)}\n"
        f"   Next: <b>{payout_dt}</b>\n"
        f"   In: <b>{fmt_countdown(payout_ts)}</b>\n\n"
        f"📋 <b>Daily Summary</b>\n"
        f"   Every day at {fmt_time(SUMMARY_HOUR_UTC, SUMMARY_MINUTE_UTC)}\n"
        f"   Next: <b>{summary_dt}</b>\n"
        f"   In: <b>{fmt_countdown(summary_ts)}</b>",
        parse_mode="HTML",
    )


async def inactive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /inactive [days] — list users who haven't claimed in over N days (default 7).
    Includes users who registered but never claimed at all.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    import time
    from datetime import datetime, timezone

    args = context.args or []
    try:
        days = int(args[0]) if args else 7
        if days < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Please provide a whole number of days ≥ 1, e.g. <code>/inactive 14</code>.", parse_mode="HTML")
        return

    cutoff = time.time() - days * 86400
    results: list[tuple[str, int, float, str]] = []  # (display_name, uid, balance, last_str)

    for key in db._db_keys_with_prefix("user:"):
        u = db.get_user_by_key(key)
        if u is None or u.get("banned"):
            continue
        last_ts = u.get("last_claim_ts", 0)
        if last_ts == 0 or last_ts < cutoff:
            uid = u.get("user_id", 0)
            uname = u.get("username") or ""
            display = f"@{uname}" if uname else f"uid:{uid}"
            bal = u.get("balance_usd", 0.0)
            last_str = (
                datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime("%Y-%m-%d")
                if last_ts else "never"
            )
            results.append((display, uid, bal, last_str))

    if not results:
        await update.message.reply_text(f"✅ No inactive users found (threshold: {days} days).")
        return

    # Sort: never-claimed first, then by oldest last claim
    results.sort(key=lambda r: (0 if r[3] == "never" else 1, r[3]))

    shown = results[:25]
    lines = [f"😴 <b>Inactive users (&gt;{days} days)</b> — {len(results)} found\n"]
    for display, uid, bal, last_str in shown:
        bal_str = f"${bal:.4f}" if bal > 0 else "$0"
        lines.append(f"• {display} (<code>{uid}</code>) — last: {last_str} — bal: {bal_str}")

    if len(results) > 25:
        lines.append(f"\n<i>Showing 25 of {len(results)}. Use /export for the full list.</i>")

    lines.append(f"\n💡 Use /broadcast to send a re-engagement message to all users.")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /search <username> — find a user by username (with or without @).
    Returns user ID, balance, status, claims, and last activity.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage: <code>/search &lt;username&gt;</code>\n"
            "Example: <code>/search satoshi</code> or <code>/search @satoshi</code>",
            parse_mode="HTML",
        )
        return

    import time
    from datetime import datetime, timezone

    query_raw = args[0].lstrip("@").lower()
    matches: list[dict] = []

    for key in db._db_keys_with_prefix("user:"):
        u = db.get_user_by_key(key)
        if u is None:
            continue
        uname = (u.get("username") or "").lower()
        if query_raw in uname:
            matches.append(u)

    if not matches:
        await update.message.reply_text(f"❌ No users found matching <code>@{query_raw}</code>.", parse_mode="HTML")
        return

    # Sort by closeness: exact match first, then partial
    matches.sort(key=lambda u: (0 if (u.get("username") or "").lower() == query_raw else 1))

    lines: list[str] = [f"🔍 <b>Search results for @{query_raw}</b> ({len(matches)} found)\n"]
    for u in matches[:10]:
        uid = u.get("user_id", "?")
        uname_display = f"@{u['username']}" if u.get("username") else f"uid:{uid}"
        bal = u.get("balance_usd", 0.0)
        earned = u.get("total_earned_usd", 0.0)
        claims = u.get("claims_count", 0)
        banned = u.get("banned", False)
        last_ts = u.get("last_claim_ts", 0)
        if last_ts:
            last_str = datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        else:
            last_str = "never"
        status = "🔴 Banned" if banned else "🟢 Active"
        lines.append(
            f"━━━━━━━━━━━━━━━\n"
            f"👤 {uname_display} (ID: <code>{uid}</code>)\n"
            f"📊 Status: {status}\n"
            f"💰 Balance: <b>${bal:.6f}</b> | Earned: <b>${earned:.6f}</b>\n"
            f"🔢 Claims: <b>{claims}</b>\n"
            f"🕒 Last claim: {last_str}"
        )

    if len(matches) > 10:
        lines.append(f"\n<i>Showing 10 of {len(matches)} matches. Narrow your search for more precise results.</i>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def topearners(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /topearners — show top 20 users by all-time total earnings.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    results: list[tuple[int, float, str]] = []
    for key in db._db_keys_with_prefix("user:"):
        u = db.get_user_by_key(key)
        if u is None:
            continue
        earned = u.get("total_earned_usd", 0.0)
        if earned > 0:
            uid = u.get("user_id", 0)
            username = u.get("username") or ""
            results.append((uid, earned, username))

    results.sort(key=lambda x: x[1], reverse=True)
    top = results[:20]

    if not top:
        await update.message.reply_text("No earnings recorded yet.")
        return

    lines = ["🏆 <b>All-Time Top Earners</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for rank, (uid, earned, username) in enumerate(top, start=1):
        icon = medals[rank - 1] if rank <= 3 else f"{rank}."
        name = f"@{username}" if username else f"uid:{uid}"
        lines.append(f"{icon} {name} — <b>${earned:.6f}</b>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def usercount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /usercount — break down total users by activity level.
    Buckets: active today, claimed this week, never claimed, banned.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    import time

    now = time.time()
    day_ago = now - 86400
    week_ago = now - 7 * 86400

    total = 0
    active_today = 0
    claimed_this_week = 0
    never_claimed = 0
    banned = 0

    for key in db._db_keys_with_prefix("user:"):
        u = db.get_user_by_key(key)
        if u is None:
            continue
        total += 1
        if u.get("banned"):
            banned += 1
            continue
        last_claim = u.get("last_claim_ts", 0)
        if last_claim == 0:
            never_claimed += 1
        elif last_claim >= day_ago:
            active_today += 1
            claimed_this_week += 1
        elif last_claim >= week_ago:
            claimed_this_week += 1

    inactive = total - active_today - claimed_this_week - never_claimed - banned
    # "claimed this week but not today" are already in claimed_this_week; split for display
    claimed_week_not_today = claimed_this_week - active_today

    def pct(n: int) -> str:
        return f"{n / total * 100:.1f}%" if total else "0%"

    await update.message.reply_text(
        f"👥 <b>User Breakdown</b>\n\n"
        f"📊 Total registered: <b>{total}</b>\n\n"
        f"🟢 Active today: <b>{active_today}</b> ({pct(active_today)})\n"
        f"🟡 Claimed this week (not today): <b>{claimed_week_not_today}</b> ({pct(claimed_week_not_today)})\n"
        f"⚪ Never claimed: <b>{never_claimed}</b> ({pct(never_claimed)})\n"
        f"🔴 Banned: <b>{banned}</b> ({pct(banned)})\n\n"
        f"<i>Percentages are out of total registered users.</i>",
        parse_mode="HTML",
    )


async def resetconfig(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /resetconfig — reset reward, cooldown, and min withdrawal to config.py defaults.
    Requires confirmation: /resetconfig confirm
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    from config import (
        CLAIM_COOLDOWN_SECONDS as DEFAULT_COOLDOWN,
        CLAIM_REWARD_USD as DEFAULT_REWARD,
        MIN_WITHDRAWAL_USD as DEFAULT_MIN,
    )

    args = context.args or []
    if not args or args[0].lower() != "confirm":
        current_reward = db.get_reward_usd()
        current_cooldown = db.get_cooldown_seconds()
        current_min = db.get_min_withdrawal_usd()
        await update.message.reply_text(
            f"⚠️ <b>This will reset all live config to defaults.</b>\n\n"
            f"Per-claim reward: <b>${current_reward:.6f}</b> → ${DEFAULT_REWARD:.6f}\n"
            f"Claim cooldown: <b>{current_cooldown}s</b> → {DEFAULT_COOLDOWN}s\n"
            f"Min withdrawal: <b>${current_min:.4f}</b> → ${DEFAULT_MIN:.4f}\n\n"
            f"To proceed, send:\n<code>/resetconfig confirm</code>",
            parse_mode="HTML",
        )
        return

    db.set_reward_usd(DEFAULT_REWARD)
    db.set_cooldown_seconds(DEFAULT_COOLDOWN)
    db.set_min_withdrawal_usd(DEFAULT_MIN)

    claims_needed = int(DEFAULT_MIN / DEFAULT_REWARD) if DEFAULT_REWARD > 0 else 0

    await update.message.reply_text(
        f"✅ <b>Configuration reset to defaults.</b>\n\n"
        f"Per-claim reward: <b>${DEFAULT_REWARD:.6f}</b>\n"
        f"Claim cooldown: <b>{DEFAULT_COOLDOWN}s</b>\n"
        f"Min withdrawal: <b>${DEFAULT_MIN:.4f}</b> ({claims_needed} claims)\n\n"
        f"All changes are live immediately.",
        parse_mode="HTML",
    )
    logger.info("Admin %d reset all live config to defaults.", user.id)


async def config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /config — display all live-configurable settings at a glance.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    from config import (
        CLAIM_COOLDOWN_SECONDS as DEFAULT_COOLDOWN,
        CLAIM_REWARD_USD as DEFAULT_REWARD,
        MIN_WITHDRAWAL_USD as DEFAULT_MIN,
    )

    reward = db.get_reward_usd()
    cooldown = db.get_cooldown_seconds()
    min_withdraw = db.get_min_withdrawal_usd()
    claims_needed = int(min_withdraw / reward) if reward > 0 else 0

    def flag(live, default) -> str:
        return "✏️" if live != default else "✅"

    await update.message.reply_text(
        f"⚙️ <b>Live Configuration</b>\n\n"
        f"{flag(reward, DEFAULT_REWARD)} <b>Per-claim reward:</b> <b>${reward:.6f}</b>"
        f"  <i>(default: ${DEFAULT_REWARD:.6f})</i>\n"
        f"   → /setreward &lt;amount&gt;\n\n"
        f"{flag(cooldown, DEFAULT_COOLDOWN)} <b>Claim cooldown:</b> <b>{cooldown}s</b>"
        f"  <i>(default: {DEFAULT_COOLDOWN}s)</i>\n"
        f"   → /setcooldown &lt;seconds&gt;\n\n"
        f"{flag(min_withdraw, DEFAULT_MIN)} <b>Min withdrawal:</b> <b>${min_withdraw:.4f}</b>"
        f"  <i>(default: ${DEFAULT_MIN:.4f})</i>\n"
        f"   → /setminwithdraw &lt;amount&gt;\n\n"
        f"📊 Users need <b>{claims_needed} claims</b> to reach the withdrawal minimum.\n\n"
        f"✅ = at default   ✏️ = overridden via DB",
        parse_mode="HTML",
    )


async def setminwithdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /setminwithdraw <amount> — change the minimum withdrawal threshold live and persist it.
    Accepts decimal values, e.g. /setminwithdraw 0.02
    Use /setminwithdraw to view the current value without changing it.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    from config import MIN_WITHDRAWAL_USD as DEFAULT_MIN

    args = context.args or []
    if not args:
        current = db.get_min_withdrawal_usd()
        reward = db.get_reward_usd()
        claims_needed = int(current / reward) if reward > 0 else 0
        await update.message.reply_text(
            f"💳 <b>Current minimum withdrawal:</b> <b>${current:.4f}</b> ({claims_needed} claims)\n"
            f"Default (config.py): ${DEFAULT_MIN:.4f}\n\n"
            f"To change it:\n<code>/setminwithdraw &lt;amount&gt;</code>\n\n"
            f"Example: <code>/setminwithdraw 0.02</code>",
            parse_mode="HTML",
        )
        return

    try:
        new_val = float(args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number, e.g. <code>0.02</code>.", parse_mode="HTML")
        return

    if new_val < 0:
        await update.message.reply_text("❌ Minimum withdrawal cannot be negative.")
        return

    if new_val == 0:
        await update.message.reply_text(
            "⚠️ Setting minimum withdrawal to $0 means users can withdraw any amount immediately.\n"
            "If you're sure, send:\n<code>/setminwithdraw 0 confirm</code>",
            parse_mode="HTML",
        )
        if len(args) < 2 or args[1].lower() != "confirm":
            return

    old_val = db.get_min_withdrawal_usd()
    db.set_min_withdrawal_usd(new_val)

    reward = db.get_reward_usd()
    claims_needed = int(new_val / reward) if reward > 0 else 0

    await update.message.reply_text(
        f"✅ <b>Minimum withdrawal updated.</b>\n\n"
        f"Old: <b>${old_val:.4f}</b> → New: <b>${new_val:.4f}</b>\n"
        f"Users now need <b>{claims_needed} claims</b> to withdraw.\n\n"
        f"Change is live immediately and will survive restarts.",
        parse_mode="HTML",
    )
    logger.info("Admin %d changed min withdrawal from $%.4f to $%.4f.", user.id, old_val, new_val)


async def setreward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /setreward <amount> — change the per-claim reward live and persist it.
    Accepts decimal values, e.g. /setreward 0.002
    Use /setreward to view the current value without changing it.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    from config import CLAIM_REWARD_USD as DEFAULT_REWARD

    args = context.args or []
    if not args:
        current = db.get_reward_usd()
        await update.message.reply_text(
            f"💰 <b>Current per-claim reward:</b> <b>${current:.6f}</b>\n"
            f"Default (config.py): ${DEFAULT_REWARD:.6f}\n\n"
            f"To change it:\n<code>/setreward &lt;amount&gt;</code>\n\n"
            f"Example: <code>/setreward 0.002</code>",
            parse_mode="HTML",
        )
        return

    try:
        new_val = float(args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number, e.g. <code>0.002</code>.", parse_mode="HTML")
        return

    if new_val < 0:
        await update.message.reply_text("❌ Reward cannot be negative.")
        return

    if new_val > 1.0:
        await update.message.reply_text(
            "⚠️ That's a very high reward ($1.00+). "
            "If you're sure, confirm by sending:\n"
            f"<code>/setreward {new_val} confirm</code>",
            parse_mode="HTML",
        )
        if len(args) < 2 or args[1].lower() != "confirm":
            return

    old_val = db.get_reward_usd()
    db.set_reward_usd(new_val)

    await update.message.reply_text(
        f"✅ <b>Per-claim reward updated.</b>\n\n"
        f"Old: <b>${old_val:.6f}</b> → New: <b>${new_val:.6f}</b>\n\n"
        f"Change is live immediately and will survive restarts.",
        parse_mode="HTML",
    )
    logger.info("Admin %d changed reward from $%.6f to $%.6f.", user.id, old_val, new_val)


async def setcooldown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /setcooldown <seconds> — change the claim cooldown live and persist it.
    Use /setcooldown to view the current value without changing it.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    from config import CLAIM_COOLDOWN_SECONDS as DEFAULT_COOLDOWN

    args = context.args or []
    if not args:
        current = db.get_cooldown_seconds()
        await update.message.reply_text(
            f"⏱ <b>Current claim cooldown:</b> <b>{current}s</b>\n"
            f"Default (config.py): {DEFAULT_COOLDOWN}s\n\n"
            f"To change it:\n<code>/setcooldown &lt;seconds&gt;</code>",
            parse_mode="HTML",
        )
        return

    try:
        new_val = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a whole number of seconds.")
        return

    if new_val < 0:
        await update.message.reply_text("❌ Cooldown cannot be negative.")
        return

    old_val = db.get_cooldown_seconds()
    db.set_cooldown_seconds(new_val)

    await update.message.reply_text(
        f"✅ <b>Claim cooldown updated.</b>\n\n"
        f"Old: <b>{old_val}s</b> → New: <b>{new_val}s</b>\n\n"
        f"Change is live immediately and will survive restarts.",
        parse_mode="HTML",
    )
    logger.info("Admin %d changed cooldown from %ds to %ds.", user.id, old_val, new_val)


async def resetleaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /resetleaderboard — wipe all daily leaderboard entries.

    Requires confirmation: /resetleaderboard confirm
    Preserves every user's total_earned_usd, referral_count, and balance.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    args = context.args or []
    if not args or args[0].lower() != "confirm":
        await update.message.reply_text(
            "⚠️ <b>This will erase all daily leaderboard entries.</b>\n\n"
            "User balances, total earnings, and referral counts are <b>not</b> affected.\n\n"
            "To proceed, send:\n<code>/resetleaderboard confirm</code>",
            parse_mode="HTML",
        )
        return

    removed = db.reset_daily_leaderboard()

    await update.message.reply_text(
        f"✅ <b>Daily leaderboard reset.</b>\n\n"
        f"Removed <b>{removed}</b> daily entry record(s).\n"
        f"All user balances, total earnings, and referral counts are intact.",
        parse_mode="HTML",
    )
    logger.info("Admin %d reset the daily leaderboard (%d keys removed).", user.id, removed)


async def export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /export — send a CSV of all users as a file attachment.
    Columns: user_id, username, balance_usd, total_claims, ltc_address,
             referral_count, total_earned_usd, banned, registered_at
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    import csv
    import io
    from datetime import datetime, timezone

    await update.message.reply_text("⏳ Building export…")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "user_id", "username", "balance_usd", "total_claims",
        "ltc_address", "referral_count", "total_earned_usd",
        "banned", "registered_at",
    ])

    count = 0
    for key in db._db_keys_with_prefix("user:"):
        u = db.get_user_by_key(key)
        if u is None:
            continue
        reg_ts = u.get("registered_at", 0)
        reg_str = (
            datetime.fromtimestamp(reg_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if reg_ts else ""
        )
        writer.writerow([
            u.get("user_id", ""),
            u.get("username", ""),
            f"{u.get('balance', 0.0):.6f}",
            u.get("total_claims", 0),
            u.get("ltc_address", ""),
            u.get("referral_count", 0),
            f"{u.get('total_earned', 0.0):.6f}",
            u.get("banned", False),
            reg_str,
        ])
        count += 1

    csv_bytes = output.getvalue().encode("utf-8")
    from datetime import date
    filename = f"faucet_users_{date.today().isoformat()}.csv"

    await update.message.reply_document(
        document=io.BytesIO(csv_bytes),
        filename=filename,
        caption=f"📊 User export — {count} users — {filename}",
    )


async def forcesummary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /forcesummary — trigger the daily summary report immediately.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    await update.message.reply_text("⏳ Generating summary…")
    from summary_job import run_daily_summary
    await run_daily_summary(context.bot)


async def adminhelp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /adminhelp — print the full admin command reference.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    text = (
        "🛠 <b>Admin Command Reference</b>\n\n"

        "<b>📊 Overview</b>\n"
        "/stats — bot-wide totals (users, claims, paid, pending)\n"
        "/pending — preview tonight's payout queue\n\n"

        "<b>💸 Payouts</b>\n"
        "/forcepayout — trigger payout batch immediately\n\n"

        "<b>🎛 Faucet Control</b>\n"
        "/pause — pause the faucet for all users\n"
        "/resume — resume the faucet\n\n"

        "<b>📢 Messaging</b>\n"
        "/broadcast — send a message to all users\n\n"

        "<b>👤 User Management</b>\n"
        "/user &lt;uid&gt; — full profile: balance, claims, referrals, address\n"
        "/addbalance &lt;uid&gt; &lt;amount&gt; — credit a user's balance\n"
        "/removebalance &lt;uid&gt; &lt;amount|all&gt; — deduct from a user's balance\n"
        "/ban &lt;uid&gt; [reason] — block a user from claiming\n"
        "/unban &lt;uid&gt; — restore a banned user's access\n\n"

        "<b>⚙️ Setup</b>\n"
        "/setadmin — get your Telegram ID for ADMIN_IDS configuration\n"
        "/adminhelp — show this reference\n\n"

        "<i>All commands are admin-only and silently blocked for regular users.</i>"
    )

    await update.message.reply_text(text, parse_mode="HTML")


async def forcepayout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /forcepayout — trigger the payout batch immediately without waiting for 00:00 UTC.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    payouts = db.get_all_pending_payouts()
    if not payouts:
        await update.message.reply_text("✅ No pending payouts to process.")
        return

    total_usd = sum(amt for _, amt in payouts)
    status_msg = await update.message.reply_text(
        f"⚙️ Starting forced payout batch…\n"
        f"👥 Users: <b>{len(payouts)}</b>\n"
        f"💰 Total: <b>${total_usd:.6f}</b>",
        parse_mode="HTML",
    )

    logger.info("Admin %d triggered forced payout batch (%d users)", user.id, len(payouts))

    from payout_job import run_daily_payouts
    await run_daily_payouts(context.bot)

    await status_msg.edit_text(
        f"✅ <b>Forced payout complete!</b>\n\n"
        f"👥 Processed: <b>{len(payouts)}</b> users\n"
        f"💰 Total sent: <b>${total_usd:.6f}</b>\n\n"
        f"Each user received a confirmation message.",
        parse_mode="HTML",
    )


async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /pending — list all users queued for today's payout batch.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    payouts = db.get_all_pending_payouts()

    if not payouts:
        await update.message.reply_text("✅ No pending payouts queued.")
        return

    payouts.sort(key=lambda x: x[1], reverse=True)
    total_usd = sum(amt for _, amt in payouts)

    lines = [
        f"⏳ <b>Pending Payouts</b> ({len(payouts)} users)\n",
        f"💰 Total to send: <b>${total_usd:.6f}</b>\n",
        f"⏰ Sends at 00:00 UTC\n",
        "━━━━━━━━━━━━━━━━━━━",
    ]

    for uid, amount in payouts[:30]:
        u = db.get_user(uid)
        username = u.get("username", str(uid)) if u else str(uid)
        address = u.get("ltc_address", "No address") if u else "No address"
        short_addr = f"{address[:10]}…" if address and address != "No address" else "⚠️ No address"
        lines.append(
            f"👤 <b>{username}</b> (<code>{uid}</code>)\n"
            f"   💵 ${amount:.6f} → <code>{short_addr}</code>"
        )

    if len(payouts) > 30:
        lines.append(f"\n<i>…and {len(payouts) - 30} more</i>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /ban <uid> [reason] — block a user from claiming.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/ban &lt;user_id&gt; [reason]</code>\n"
            "Example: <code>/ban 123456789 abuse</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID — must be an integer.")
        return

    if target_uid == user.id:
        await update.message.reply_text("❌ You cannot ban yourself.")
        return

    target = db.get_user(target_uid)
    if target is None:
        await update.message.reply_text(
            f"❌ No user found with ID <code>{target_uid}</code>.", parse_mode="HTML"
        )
        return

    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason given"
    target["banned"] = True
    target["ban_reason"] = reason
    db.save_user(target)

    username = target.get("username", str(target_uid))
    logger.info("Admin %d banned uid=%d (%s)", user.id, target_uid, reason)

    await update.message.reply_text(
        f"🔨 <b>User banned!</b>\n\n"
        f"👤 {username} (<code>{target_uid}</code>)\n"
        f"📝 Reason: {reason}",
        parse_mode="HTML",
    )

    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text=(
                f"🚫 <b>You have been banned</b>\n\n"
                f"Reason: {reason}\n\n"
                f"Contact support if you believe this is a mistake."
            ),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning("Could not notify banned uid=%d: %s", target_uid, exc)


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /unban <uid> — restore a banned user's access.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/unban &lt;user_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID — must be an integer.")
        return

    target = db.get_user(target_uid)
    if target is None:
        await update.message.reply_text(
            f"❌ No user found with ID <code>{target_uid}</code>.", parse_mode="HTML"
        )
        return

    if not target.get("banned"):
        await update.message.reply_text(
            f"ℹ️ User <code>{target_uid}</code> is not banned.", parse_mode="HTML"
        )
        return

    target["banned"] = False
    target["ban_reason"] = None
    db.save_user(target)

    username = target.get("username", str(target_uid))
    logger.info("Admin %d unbanned uid=%d", user.id, target_uid)

    await update.message.reply_text(
        f"✅ <b>User unbanned!</b>\n\n"
        f"👤 {username} (<code>{target_uid}</code>) can claim again.",
        parse_mode="HTML",
    )

    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text="✅ <b>Your ban has been lifted.</b>\n\nYou can now claim again. Welcome back!",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning("Could not notify unbanned uid=%d: %s", target_uid, exc)


async def user_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /user <uid> — show full profile for a user.
    """
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/user &lt;user_id&gt;</code>\n"
            "Example: <code>/user 123456789</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID — must be an integer.")
        return

    target = db.get_user(target_uid)
    if target is None:
        await update.message.reply_text(
            f"❌ No user found with ID <code>{target_uid}</code>.", parse_mode="HTML"
        )
        return

    import time
    from datetime import datetime, timezone

    username = target.get("username", "—")
    balance = target.get("balance_usd", 0.0)
    total_earned = target.get("total_earned_usd", 0.0)
    claims = target.get("claims_count", 0)
    referral_count = target.get("referral_count", 0)
    referral_earned = target.get("referral_earnings_generated_usd", 0.0)
    referrer_uid = target.get("referrer_uid")
    ltc_address = target.get("ltc_address") or "Not set"
    withdrawal_queued = target.get("withdrawal_queued", False)
    pending_payout = db.get_pending_payout(target_uid)
    last_claim_ts = target.get("last_claim_ts", 0)
    registered_at = target.get("registered_at", 0)

    def fmt_ts(ts: float) -> str:
        if not ts:
            return "Never"
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    referrer_line = f"<code>{referrer_uid}</code>" if referrer_uid else "None"

    text = (
        f"👤 <b>User Profile</b>\n\n"
        f"🆔 ID: <code>{target_uid}</code>\n"
        f"👤 Username: <b>{username}</b>\n"
        f"📅 Registered: {fmt_ts(registered_at)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance: <b>${balance:.6f}</b>\n"
        f"📊 Total earned: <b>${total_earned:.6f}</b>\n"
        f"🔢 Claims: <b>{claims}</b>\n"
        f"🕐 Last claim: {fmt_ts(last_claim_ts)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Referrals made: <b>{referral_count}</b>\n"
        f"🤝 Referral earnings: <b>${referral_earned:.6f}</b>\n"
        f"🔗 Referred by: {referrer_line}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📬 LTC address: <code>{ltc_address}</code>\n"
        f"⏳ Queued payout: <b>${pending_payout:.6f}</b>\n"
        f"🔄 Withdrawal queued: {'Yes' if withdrawal_queued else 'No'}"
    )

    await update.message.reply_text(text, parse_mode="HTML")


def build_broadcast_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_WAITING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send),
            ],
        },
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
    )


async def setadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /setadmin <uid> — grant admin to a user (only works if ADMIN_IDS is empty,
    i.e. the very first admin bootstrapping).
    """
    user = update.effective_user
    if user is None:
        return

    # Allow if no admins configured yet OR caller is already admin
    if ADMIN_IDS and not _is_admin(user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    if not context.args:
        await update.message.reply_text(
            f"ℹ️ Your Telegram ID is <code>{user.id}</code>.\n\n"
            f"Add it to the <b>ADMIN_IDS</b> environment variable to enable admin commands.\n"
            f"Example: <code>ADMIN_IDS={user.id}</code>",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        f"ℹ️ To make <code>{context.args[0]}</code> an admin, add their ID to the "
        f"<b>ADMIN_IDS</b> environment variable.",
        parse_mode="HTML",
    )
