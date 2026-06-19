"""
FaucetPay and CoinGecko API helpers.
"""

from __future__ import annotations

import logging

import aiohttp

from config import (
    FAUCETPAY_API_KEY,
    FAUCETPAY_API_URL,
    FAUCETPAY_CURRENCY,
    COINGECKO_URL,
)

logger = logging.getLogger(__name__)


async def get_ltc_price_usd() -> float | None:
    """Fetch current LTC/USD price from CoinGecko. Returns None on failure."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                return float(data["litecoin"]["usd"])
    except Exception as exc:
        logger.error("CoinGecko fetch failed: %s", exc)
        return None


def usd_to_satoshi_ltc(amount_usd: float, ltc_price_usd: float) -> int:
    """Convert USD amount to LTC satoshis (1 LTC = 100_000_000 satoshis)."""
    ltc_amount = amount_usd / ltc_price_usd
    return int(ltc_amount * 100_000_000)


async def send_ltc_payout(
    ltc_address: str,
    amount_usd: float,
    ltc_price_usd: float,
) -> dict:
    """
    Send LTC payout via FaucetPay API.

    Returns dict with keys:
      success (bool), message (str), payout_id (str | None)
    """
    satoshis = usd_to_satoshi_ltc(amount_usd, ltc_price_usd)

    payload = {
        "api_key": FAUCETPAY_API_KEY,
        "to": ltc_address,
        "amount": satoshis,
        "currency": FAUCETPAY_CURRENCY,
        "referral": "true",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                FAUCETPAY_API_URL,
                data=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                logger.info("FaucetPay response for %s: %s", ltc_address, data)

                status = data.get("status", 999)
                if status == 200:
                    return {
                        "success": True,
                        "message": data.get("message", "OK"),
                        "payout_id": str(data.get("payout_id", "")),
                    }
                else:
                    return {
                        "success": False,
                        "message": data.get("message", f"API error {status}"),
                        "payout_id": None,
                    }
    except Exception as exc:
        logger.error("FaucetPay request failed: %s", exc)
        return {"success": False, "message": str(exc), "payout_id": None}
