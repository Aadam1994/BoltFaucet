import os

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

# ── FaucetPay ─────────────────────────────────────────────────────────────────
FAUCETPAY_API_KEY: str = os.environ["FAUCETPAY_API_KEY"]
FAUCETPAY_API_URL: str = "https://faucetpay.io/api/v1/send"
FAUCETPAY_CURRENCY: str = "LTC"

# ── Faucet mechanics ──────────────────────────────────────────────────────────
CLAIM_REWARD_USD: float = 0.001          # $0.001 per claim
CLAIM_COOLDOWN_SECONDS: int = 10         # 10 seconds between claims
MIN_WITHDRAWAL_USD: float = 0.05         # minimum $0.05 to withdraw (50 claims)
REFERRAL_BONUS_PERCENT: float = 0.15     # 15% of referral earnings go to referrer

# ── Payout schedule ───────────────────────────────────────────────────────────
PAYOUT_HOUR_UTC: int = 0                 # daily payout at 00:00 UTC
PAYOUT_MINUTE_UTC: int = 0

# ── Daily summary ─────────────────────────────────────────────────────────────
SUMMARY_HOUR_UTC: int = 9                # daily summary sent to admins at 09:00 UTC
SUMMARY_MINUTE_UTC: int = 0

# ── Admin ─────────────────────────────────────────────────────────────────────
# Comma-separated Telegram user IDs that have admin access
_admin_ids_raw: str = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS: set[int] = (
    {int(i.strip()) for i in _admin_ids_raw.split(",") if i.strip()}
    if _admin_ids_raw
    else set()
)

# ── CoinGecko ─────────────────────────────────────────────────────────────────
COINGECKO_URL: str = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=litecoin&vs_currencies=usd"
)

# ── Anti-abuse thresholds ─────────────────────────────────────────────────────
# Referral burst: alert if a referrer gains this many referrals within the window
ABUSE_REFERRAL_BURST_COUNT: int = 5
ABUSE_REFERRAL_BURST_WINDOW_MINUTES: int = 60

# Claim ring: alert if this many of a referrer's users all claim within the window
ABUSE_RING_MIN_MEMBERS: int = 5
ABUSE_RING_WINDOW_MINUTES: int = 30

# Claim spike: alert if a single user makes this many claims within the window
ABUSE_CLAIM_SPIKE_COUNT: int = 20
ABUSE_CLAIM_SPIKE_WINDOW_MINUTES: int = 10

# ── Misc ──────────────────────────────────────────────────────────────────────
LEADERBOARD_SIZE: int = 10
ADS_PER_CLAIM: int = 2                   # simulated ad watches required per claim
