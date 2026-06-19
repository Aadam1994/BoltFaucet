"""
Thin async wrapper around Replit Database (replit.db).

Keys used
─────────────────────────────────────────────────────────────────────────────
user:<uid>              → dict  (see _default_user)
pending_payout:<uid>    → float (USD amount queued for payout)
faucet_paused          → "1" | absent
daily_top:<YYYY-MM-DD>  → dict  {uid: float_usd}  (earnings today per user)
stats                   → dict  {total_users, total_paid_usd, total_claims}
"""

from __future__ import annotations

import json
import time
from datetime import date, timezone
from typing import Any

from replit import db  # type: ignore[import]


# ── helpers ───────────────────────────────────────────────────────────────────

def _get(key: str, default: Any = None) -> Any:
    raw = db.get(key)
    if raw is None:
        return default
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _set(key: str, value: Any) -> None:
    db[key] = json.dumps(value) if not isinstance(value, str) else value


def _default_user(uid: int, username: str | None = None) -> dict:
    return {
        "uid": uid,
        "username": username or str(uid),
        "balance_usd": 0.0,
        "total_earned_usd": 0.0,
        "claims_count": 0,
        "last_claim_ts": 0,          # Unix timestamp of last successful claim
        "referrer_uid": None,        # UID of who referred this user
        "referral_count": 0,
        "ltc_address": None,
        "withdrawal_queued": False,
        "ads_watched": 0,            # ads watched in current claim cycle
        "captcha_pending": False,    # True after ads watched, waiting for captcha
        "registered_at": time.time(),
    }


# ── user ──────────────────────────────────────────────────────────────────────

def get_user(uid: int) -> dict | None:
    return _get(f"user:{uid}")


def get_or_create_user(uid: int, username: str | None = None) -> dict:
    user = get_user(uid)
    if user is None:
        user = _default_user(uid, username)
        _set(f"user:{uid}", user)
        # bump total_users in stats
        stats = get_stats()
        stats["total_users"] += 1
        save_stats(stats)
    return user


def save_user(user: dict) -> None:
    _set(f"user:{user['uid']}", user)


# ── stats ─────────────────────────────────────────────────────────────────────

def _default_stats() -> dict:
    return {"total_users": 0, "total_paid_usd": 0.0, "total_claims": 0}


def get_stats() -> dict:
    return _get("stats", _default_stats())


def save_stats(stats: dict) -> None:
    _set("stats", stats)


# ── payout queue ──────────────────────────────────────────────────────────────

def queue_payout(uid: int, amount_usd: float) -> None:
    existing = _get(f"pending_payout:{uid}", 0.0)
    _set(f"pending_payout:{uid}", existing + amount_usd)


def get_pending_payout(uid: int) -> float:
    return _get(f"pending_payout:{uid}", 0.0)


def clear_pending_payout(uid: int) -> None:
    try:
        del db[f"pending_payout:{uid}"]
    except KeyError:
        pass


def get_all_pending_payouts() -> list[tuple[int, float]]:
    """Return list of (uid, amount_usd) for all users with pending payouts."""
    results: list[tuple[int, float]] = []
    for key in db.keys():
        if key.startswith("pending_payout:"):
            uid = int(key.split(":")[1])
            amount = _get(key, 0.0)
            if amount > 0:
                results.append((uid, amount))
    return results


# ── daily leaderboard ─────────────────────────────────────────────────────────

def _today_key() -> str:
    return f"daily_top:{date.today(timezone.utc).isoformat()}"


def add_daily_earnings(uid: int, amount_usd: float) -> None:
    key = _today_key()
    board: dict = _get(key, {})
    board[str(uid)] = board.get(str(uid), 0.0) + amount_usd
    _set(key, board)


def get_top_referrers(limit: int = 10) -> list[tuple[int, float]]:
    """Return top referrers sorted by total earnings they generated for themselves via referrals."""
    results: list[tuple[int, float]] = []
    for key in db.keys():
        if key.startswith("user:"):
            user = _get(key)
            if isinstance(user, dict):
                earned = user.get("referral_earnings_generated_usd", 0.0)
                if earned > 0:
                    results.append((user["uid"], earned))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def get_daily_leaderboard() -> list[tuple[int, float]]:
    key = _today_key()
    board: dict = _get(key, {})
    sorted_items = sorted(board.items(), key=lambda x: x[1], reverse=True)
    return [(int(uid), amount) for uid, amount in sorted_items]


def get_min_withdrawal_usd() -> float:
    """Return the current minimum withdrawal threshold, live from DB or fall back to config default."""
    from config import MIN_WITHDRAWAL_USD
    return float(_get("config:min_withdrawal_usd", MIN_WITHDRAWAL_USD))


def set_min_withdrawal_usd(amount: float) -> None:
    """Persist a new minimum withdrawal threshold to the DB."""
    _set("config:min_withdrawal_usd", amount)


def get_reward_usd() -> float:
    """Return the current per-claim reward, live from DB or fall back to config default."""
    from config import CLAIM_REWARD_USD
    return float(_get("config:reward_usd", CLAIM_REWARD_USD))


def set_reward_usd(amount: float) -> None:
    """Persist a new per-claim reward value to the DB."""
    _set("config:reward_usd", amount)


def get_cooldown_seconds() -> int:
    """Return the current claim cooldown, live from DB or fall back to config default."""
    from config import CLAIM_COOLDOWN_SECONDS
    return int(_get("config:cooldown_seconds", CLAIM_COOLDOWN_SECONDS))


def set_cooldown_seconds(seconds: int) -> None:
    """Persist a new claim cooldown value to the DB."""
    _set("config:cooldown_seconds", seconds)


def reset_daily_leaderboard() -> int:
    """
    Delete all daily_top:* keys, wiping the daily leaderboard.
    Returns the number of keys removed.
    User records (total_earned, referral_count, balance) are untouched.
    """
    keys_to_delete = [k for k in db.keys() if k.startswith("daily_top:")]
    for k in keys_to_delete:
        db.delete(k)
    return len(keys_to_delete)


# ── faucet pause flag ─────────────────────────────────────────────────────────

def _db_keys_with_prefix(prefix: str):
    """Yield all db keys that start with the given prefix."""
    for key in db.keys():
        if key.startswith(prefix):
            yield key


def get_user_by_key(key: str) -> dict | None:
    """Fetch a user record directly by its db key (e.g. 'user:123')."""
    return _get(key)


def get_all_user_ids() -> list[int]:
    """Return all registered user IDs."""
    ids: list[int] = []
    for key in db.keys():
        if key.startswith("user:"):
            try:
                ids.append(int(key.split(":")[1]))
            except ValueError:
                pass
    return ids


def is_faucet_paused() -> bool:
    return db.get("faucet_paused") == "1"


def set_faucet_paused(paused: bool) -> None:
    if paused:
        db["faucet_paused"] = "1"
    else:
        try:
            del db["faucet_paused"]
        except KeyError:
            pass
