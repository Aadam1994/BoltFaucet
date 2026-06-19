"""
Inline keyboard builders.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Claim", callback_data="claim"),
            InlineKeyboardButton("💼 Balance", callback_data="balance"),
        ],
        [
            InlineKeyboardButton("🏆 Earners", callback_data="top"),
            InlineKeyboardButton("🤝 Referrers", callback_data="referrers"),
        ],
        [
            InlineKeyboardButton("👥 My Referral", callback_data="referral"),
            InlineKeyboardButton("💸 Withdraw", callback_data="withdraw"),
        ],
    ])


def watch_ad_keyboard(ad_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📺 Watch Ad {ad_number}/2", callback_data=f"watch_ad_{ad_number}")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu")],
    ])


def captcha_keyboard() -> InlineKeyboardMarkup:
    """Simple inline math captcha — user picks the correct answer."""
    import random
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    correct = a + b
    # Generate 3 wrong answers
    wrong = set()
    while len(wrong) < 3:
        w = random.randint(1, 18)
        if w != correct:
            wrong.add(w)
    options = [correct] + list(wrong)
    random.shuffle(options)

    buttons = [
        InlineKeyboardButton(str(opt), callback_data=f"captcha_{opt}_{correct}")
        for opt in options
    ]
    row1 = buttons[:2]
    row2 = buttons[2:]
    return (
        f"{a} + {b} = ?",
        InlineKeyboardMarkup([row1, row2, [InlineKeyboardButton("🔙 Back", callback_data="menu")]]),
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")],
    ])


def set_address_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Set LTC Address", callback_data="set_address")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu")],
    ])
