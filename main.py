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

    # رسالة كبيرة و منظمة
    text = f"""💎 <b>مرحبا {name}</b> 💎

━━━━━━━━━━
🏦 <b>محفظتك:</b> <code>{user['balance']:.5f} LTC</code>
🎯 <b>الحد الأدنى للسحب:</b> 0.001 LTC
👤 <b>عنوانك:</b> <code>{user['address']}</code>
━━━━━━━━━━

اختر من القائمة بالأسفل 👇
"""
    # كل البوتونات يبانو
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎬 مشاهدة إعلانات", callback_data="claim")
    btn2 = types.InlineKeyboardButton("💰 رصيدي", callback_data="balance")
    btn3 = types.InlineKeyboardButton("💸 سحب", callback_data="withdraw")
    btn4 = types.InlineKeyboardButton("🏆 المتصدرين", callback_data="top")
    btn5 = types.InlineKeyboardButton("👥 دعوة أصدقاء", callback_data="referrals")
    btn6 = types.InlineKeyboardButton("📩 ضبط العنوان", callback_data="setaddress")
    keyboard.add(btn1, btn2, btn3, btn4, btn5, btn6)

    bot.send_message(msg.chat.id, text, reply_markup=keyboard, parse_mode="HTML")

# باقي الفانكشنز كيف
@bot.message_handler(commands=['claim'])
def claim(msg):
    user = get_user(msg)
    user['balance'] += 0.00001
    bot.send_message(msg.chat.id, f"✅ <b>تم!</b>\nربحت <code>+0.00001 LTC</code>\nرصيدك الجديد: <code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

@bot.message_handler(commands=['balance'])
def balance(msg):
    user = get_user(msg)
    bot.send_message(msg.chat.id, f"💰 <b>رصيدك الحالي:</b>\n<code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

@bot.message_handler(commands=['withdraw'])
def withdraw(msg):
    user = get_user(msg)
    if user['balance'] >= 0.001:
        bot.send_message(msg.chat.id, f"💸 <b>تم طلب السحب بنجاح ✅</b>")
        user['balance'] = 0
    else:
        bot.send_message(msg.chat.id, f"❌ <b>الحد الأدنى للسحب 0.001 LTC</b>\nرصيدك: <code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

@bot.message_handler(commands=['top'])
def top(msg): bot.send_message(msg.chat.id, "🏆 <b>قائمة المتصدرين:</b>\n1. Adam - 0.5 LTC\n2. انت - 0.0 LTC", parse_mode="HTML")

@bot.message_handler(commands=['referrals'])
def referrals(msg):
    link = f"https://t.me/{bot.get_me().username}?start={msg.from_user.id}"
    bot.send_message(msg.chat.id, f"👥 <b>رابط الدعوة تاعك:</b>\n<code>{link}</code>\nتربح 10% من ارباح اصدقائك", parse_mode="HTML")

@bot.message_handler(commands=['setaddress'])
def setaddress(msg): bot.send_message(msg.chat.id, "📩 <b>ابعثلي عنوان محفظة LTC تاعك ضرك</b>")

@bot.message_handler(func=lambda m: True)
def save_address(msg):
    user = get_user(msg)
    if msg.text.startswith("L") or msg.text.startswith("M"):
        user['address'] = msg.text
        bot.send_message(msg.chat.id, f"✅ <b>تم حفظ العنوان:</b>\n<code>{msg.text}</code>", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "claim": claim(call.message)
    elif call.data == "balance": balance(call.message)
    elif call.data == "withdraw": withdraw(call.message)
    elif call.data == "top": top(call.message)
    elif call.data == "referrals": referrals(call.message)
    elif call.data == "setaddress": setaddress(call.message)
    bot.answer_callback_query(call.id)

if __name__ == "__main__":
    bot.polling(none_stop=True)
