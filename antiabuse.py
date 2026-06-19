"""
Anti-abuse detection — runs after every successful claim.

Checks performed
────────────────────────────────────────────────────────────────────────────
1. REFERRAL BURST
   A referrer gained ABUSE_REFERRAL_BURST_COUNT or more new referrals within
   ABUSE_REFERRAL_BURST_WINDOW_MINUTES. Typical of someone creating throwaway
   accounts to farm referral bonuses.

2. REFERRAL CLAIM RING
   ABUSE_RING_MIN_MEMBERS or more users who share the same referrer all
   completed a claim within ABUSE_RING_WINDOW_MINUTES of each other.
   Indicates a coordinated claim ring.

3. SINGLE-USER CLAIM SPIKE
   A single user has made ABUSE_CLAIM_SPIKE_COUNT or more claims in the last
   ABUSE_CLAIM_SPIKE_WINDOW_MINUTES. Useful as a sanity check even though the
   cooldown should already limit this.

Each check fires at most once per (uid / referrer_uid) per hour to avoid
alert spam — tracked via an in-memory cooldown dict (resets on bot restart).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from telegram import Bot

import database as db
from config import (
    ABUSE_CLAIM_SPIKE_COUNT,
    ABUSE_CLAIM_SPIKE_WINDOW_MINUTES,
    ABUSE_REFERRAL_BURST_COUNT,
    ABUSE_REFERRAL_BURST_WINDOW_MINUTES,
    ABUSE_RING_MIN_MEMBERS,
    ABUSE_RING_WINDOW_MINUTES,
    ADMIN_IDS,
)

logger = logging.getLogger(__name__)

# In-memory alert cooldown: key → last alert timestamp
# Prevents spamming the same alert every claim
_alert_cooldown: dict[str, float] = defaultdict(float)
ALERT_COOLDOWN_SECONDS = 3600  # 1 hour between identical alerts


def _should_alert(key: str) -> bool:
    """Return True if enough time has passed since the last alert for this key."""
    now = time.time()
    if now - _alert_cooldown[key] >= ALERT_COOLDOWN_SECONDS:
        _alert_cooldown[key] = now
        return True
    return False


async def _send_alert(bot: Bot, text: str) -> None:
    """Send an alert message to every configured admin."""
    if not ADMIN_IDS:
        logger.warning("Abuse detected but no ADMIN_IDS configured — alert not sent.")
        return
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.error("Failed to send abuse alert to admin %d: %s", admin_id, exc)


async def run_checks(bot: Bot, claimer_uid: int) -> None:
    """
    Entry point — call this after every successful claim.
    Runs all abuse checks for the given claimer.
    """
    claimer = db.get_user(claimer_uid)
    if claimer is None:
        return

    await _check_claim_spike(bot, claimer)

    referrer_uid = claimer.get("referrer_uid")
    if referrer_uid:
        referrer = db.get_user(referrer_uid)
        if referrer:
            await _check_referral_burst(bot, referrer)
            await _check_referral_claim_ring(bot, referrer, claimer_uid)


# ── Check 1: single-user claim spike ─────────────────────────────────────────

async def _check_claim_spike(bot: Bot, claimer: dict) -> None:
    uid = claimer["uid"]
    claims = claimer.get("claims_count", 0)
    window_mins = ABUSE_CLAIM_SPIKE_WINDOW_MINUTES

    # Use claim_timestamps list if available, otherwise approximate from last_claim_ts
    timestamps: list[float] = claimer.get("claim_timestamps", [])
    cutoff = time.time() - window_mins * 60
    recent = [ts for ts in timestamps if ts >= cutoff]

    if len(recent) >= ABUSE_CLAIM_SPIKE_COUNT:
        key = f"spike:{uid}"
        if _should_alert(key):
            username = claimer.get("username", str(uid))
            logger.warning("ABUSE claim spike uid=%d claims_in_window=%d", uid, len(recent))
            await _send_alert(
                bot,
                f"⚠️ <b>Abuse Alert: Claim Spike</b>\n\n"
                f"👤 User: <b>{username}</b> (<code>{uid}</code>)\n"
                f"🔢 Claims in last {window_mins}min: <b>{len(recent)}</b>\n"
                f"📊 Total claims: <b>{claims}</b>\n\n"
                f"Use /user {uid} to inspect · /ban {uid} to block",
            )


# ── Check 2: referral burst ───────────────────────────────────────────────────

async def _check_referral_burst(bot: Bot, referrer: dict) -> None:
    uid = referrer["uid"]
    timestamps: list[float] = referrer.get("referral_join_timestamps", [])
    cutoff = time.time() - ABUSE_REFERRAL_BURST_WINDOW_MINUTES * 60
    recent = [ts for ts in timestamps if ts >= cutoff]

    if len(recent) >= ABUSE_REFERRAL_BURST_COUNT:
        key = f"refburst:{uid}"
        if _should_alert(key):
            username = referrer.get("username", str(uid))
            total_refs = referrer.get("referral_count", 0)
            logger.warning(
                "ABUSE referral burst uid=%d refs_in_window=%d", uid, len(recent)
            )
            await _send_alert(
                bot,
                f"⚠️ <b>Abuse Alert: Referral Burst</b>\n\n"
                f"👤 Referrer: <b>{username}</b> (<code>{uid}</code>)\n"
                f"👥 New referrals in last {ABUSE_REFERRAL_BURST_WINDOW_MINUTES}min: "
                f"<b>{len(recent)}</b>\n"
                f"👥 Total referrals: <b>{total_refs}</b>\n\n"
                f"Use /user {uid} to inspect · /ban {uid} to block",
            )


# ── Check 3: referral claim ring ──────────────────────────────────────────────

async def _check_referral_claim_ring(
    bot: Bot, referrer: dict, new_claimer_uid: int
) -> None:
    """
    Check if multiple users under the same referrer all claimed recently,
    suggesting a coordinated claim ring.
    """
    referrer_uid = referrer["uid"]
    cutoff = time.time() - ABUSE_RING_WINDOW_MINUTES * 60

    # Scan all users to find referrals of this referrer who claimed recently
    recent_claimers: list[int] = []
    for key in db._db_keys_with_prefix("user:"):
        u = db.get_user_by_key(key)
        if u is None:
            continue
        if u.get("referrer_uid") != referrer_uid:
            continue
        last_claim = u.get("last_claim_ts", 0)
        if last_claim >= cutoff:
            recent_claimers.append(u["uid"])

    if len(recent_claimers) >= ABUSE_RING_MIN_MEMBERS:
        key = f"ring:{referrer_uid}"
        if _should_alert(key):
            username = referrer.get("username", str(referrer_uid))
            logger.warning(
                "ABUSE claim ring referrer=%d members=%d",
                referrer_uid,
                len(recent_claimers),
            )
            member_ids = ", ".join(f"<code>{uid}</code>" for uid in recent_claimers[:8])
            overflow = f" +{len(recent_claimers) - 8} more" if len(recent_claimers) > 8 else ""
            await _send_alert(
                bot,
                f"⚠️ <b>Abuse Alert: Claim Ring</b>\n\n"
                f"👤 Referrer: <b>{username}</b> (<code>{referrer_uid}</code>)\n"
                f"🔁 Referrals claiming in last {ABUSE_RING_WINDOW_MINUTES}min: "
                f"<b>{len(recent_claimers)}</b>\n"
                f"🆔 Members: {member_ids}{overflow}\n\n"
                f"Use /user {referrer_uid} to inspect · /ban {referrer_uid} to block",
            )
