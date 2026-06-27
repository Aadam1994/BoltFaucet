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
    btn2 = types.InlineKeyboardButton("💰 رصيدي", callback_data="balance") # هنا كان الخطأ، كان ناقص
    btn3 = types.InlineKeyboardButton("💸 سحب", callback_data="withdraw")
    btn4 = types.InlineKeyboardButton("🏆 المتصدرين", callback_data="top")
    btn5 = types.InlineKeyboardButton("👥 دعوة أصدقاء", callback_data="referrals")
    btn6 = types.InlineKeyboardButton("📩 ضبط العنوان", callback_data="setaddress")
    keyboard.add(btn1, btn2, btn3, btn4, btn5, btn6) # هنا زدناها

    bot.send_message(msg.chat.id, text, reply_markup=keyboard)

@bot.message_handler(commands=['claim'])
def claim(msg):
    user = get
