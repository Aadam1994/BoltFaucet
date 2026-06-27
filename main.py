import telebot
from telebot import types

TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU"
bot = telebot.TeleBot(TOKEN)

# قاعدة بيانات مؤقتة
user_data = {}

def get_user(msg):
    uid = msg.from_user.id
    if uid not in user_data:
        user_data[uid] = {"balance": 0.0, "address": "غير مضبوط"}
    return user_data[uid]

@bot.message_handler(commands=['start'])
def start(msg):
    user = get_user(msg)
    name = msg.from_user.first_name
    text = f"""💎 مرحبا {name}

أنت الآن في بوت Ltc Earn Faucet
رصيدك الحالي: {user['balance']} LTC
السحب يبدأ من: 0.001 LTC
"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎬 مشاهدة إعلانات", callback_data="claim")
    btn2 = types.InlineKeyboardButton("💰 رصيد
