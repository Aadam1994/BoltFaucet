import telebot
from telebot import types

TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU"
bot = telebot.TeleBot(TOKEN)

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
    keyboard.add(
        types.InlineKeyboardButton("🎬 مشاهدة إعلانات", callback_data="claim"),
        types.InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
    )
    bot.send_message(msg.chat.id, text, reply_markup=keyboard)

@bot.message_handler(commands=['claim'])
def claim(msg):
    user = get_user(msg)
    user['balance'] += 0.00001
    bot.send_message(msg.chat.id, f"✅ تم! رصيدك: {user['balance']} LTC")

@bot.message_handler(commands=['balance'])
def balance(msg):
    user = get_user(msg)
    bot.send_message(msg.chat.id, f"💰 رصيدك: {user['balance']} LTC")

if __name__ == "__main__":
    bot.polling(none_stop=True, skip_pending=True, interval=0)
