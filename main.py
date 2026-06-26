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

    text = f"""💎 مرحبا {name} | Welcome {name}

أنت الآن في بوت Ltc Earn Faucet
رصيدك الحالي: {user['balance']} LTC
السحب يبدأ من: 0.001 LTC
"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎬 مشاهدة إعلانات", callback_data="claim")
    btn2 = types.InlineKeyboardButton("💰 رصيدي", callback_data="balance")
    btn3 = types.InlineKeyboardButton("👥 دعوة أصدقاء", callback_data="ref")
    btn4 = types.InlineKeyboardButton("💸 سحب", callback_data="withdraw")
    keyboard.add(btn1, btn2, btn3, btn4)

    bot.send_message(msg.chat.id, text, reply_markup=keyboard)

@bot.message_handler(commands=['claim'])
def claim(msg):
    user = get_user(msg)
    user['balance'] += 0.00001
    bot.send_message(msg.chat.id, f"✅ تم! ربحت 0.00001 LTC\nرصيدك: {user['balance']} LTC")

@bot.message_handler(commands=['balance'])
def balance(msg):
    user = get_user(msg)
    bot.send_message(msg.chat.id, f"💰 رصيدك الحالي: {user['balance']} LTC")

@bot.message_handler(commands=['withdraw'])
def withdraw(msg):
    user = get_user(msg)
    if user['balance'] >= 0.001:
        bot.send_message(msg.chat.id, f"💸 تم طلب السحب. رصيدك: {user['balance']} LTC")
        user['balance'] = 0
    else:
        bot.send_message(msg.chat.id, f"❌ الحد الأدنى للسحب 0.001 LTC\nرصيدك: {user['balance']} LTC")

@bot.message_handler(commands=['top'])
def top(msg):
    bot.send_message(msg.chat.id, "🏆 قائمة المتصدرين:\n1. Adam - 0.5 LTC\n2. انت - 0.0 LTC")

@bot.message_handler(commands=['referrals'])
def referrals(msg):
    uid = msg.from_user.id
    bot.send_message(msg.chat.id, f"👥 رابط الدعوة تاعك:\nhttps://t.me/{bot.get_me().username}?start={uid}\nتربح 10% من ارباح اصدقائك")

@bot.message_handler(commands=['setaddress'])
def setaddress(msg):
    bot.send_message(msg.chat.id, "📩 ابعثلي عنوان محفظة LTC تاعك ضرك")

@bot.message_handler(func=lambda m: True)
def save_address(msg):
    user = get_user(msg)
    if "L" in msg.text or "ltc" in msg.text.lower():
        user['address'] = msg
