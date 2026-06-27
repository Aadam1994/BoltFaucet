import telebot
from telebot import types

TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU"
bot = telebot.TeleBot(TOKEN)

user_data = {}

def get_user(msg):
    uid = msg.from_user.id
    if uid not in user_data:
        user_data[uid] = {"balance": 0.0, "address": "غير محدد"}
    return user_data[uid]

@bot.message_handler(commands=['start'])
def start(msg):
    user = get_user(msg)
    name = msg.from_user.first_name

    text = f"""✨ <b>مرحباً بك في Ltc Earn Faucet</b> ✨

<b>▫️ الاسم:</b> {name}
<b>▫️ الرصيد الحالي:</b> <code>{user['balance']:.5f} LTC</code>
<b>▫️ عنوان المحفظة:</b> <code>{user['address']}</code>
<b>▫️ الحد الأدنى للسحب:</b> 0.001 LTC

اختر العملية التي تريدها من الأسفل:
"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🎥 مشاهدة الإعلانات", callback_data="claim"),
        types.InlineKeyboardButton("💳 عرض الرصيد", callback_data="balance"),
        types.InlineKeyboardButton("💵 طلب سحب", callback_data="withdraw"),
        types.InlineKeyboardButton("🏅 لوحة المتصدرين", callback_data="top"),
        types.InlineKeyboardButton("🤝 نظام الإحالة", callback_data="referrals"),
        types.InlineKeyboardButton("📮 تغيير العنوان", callback_data="setaddress")
    )
    bot.send_message(msg.chat.id, text, reply_markup=keyboard, parse_mode="HTML")

@bot.message_handler(commands=['claim'])
def claim(msg):
    user = get_user(msg)
    user['balance'] += 0.00001
    bot.send_message(msg.chat.id, f"✅ <b>تم إضافة الأرباح بنجاح</b>\n\n+ 0.00001 LTC\nرصيدك الجديد: <code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

@bot.message_handler(commands=['balance'])
def balance(msg):
    user = get_user(msg)
    bot.send_message(msg.chat.id, f"💳 <b>رصيدك الحالي</b>\n\n<code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

@bot.message_handler(commands=['withdraw'])
def withdraw(msg):
    user = get_user(msg)
    if user['balance'] >= 0.001:
        bot.send_message(msg.chat.id, f"✅ <b>تم استلام طلب السحب</b>\n\nسيتم تحويل <code>{user['balance']:.5f} LTC</code> إلى محفظتك قريباً.", parse_mode="HTML")
        user['balance'] = 0
    else:
        bot.send_message(msg.chat.id, f"❌ <b>رصيدك غير كافي للسحب</b>\n\nالحد الأدنى: <code>0.001 LTC</code>\nرصيدك: <code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

@bot.message_handler(commands=['top'])
def top(msg):
    bot.send_message(msg.chat.id, "🏅 <b>لوحة المتصدرين</b>\n\n1. Adam - <code>0.50000 LTC</code>\n2. أنت - <code>0.00000 LTC</code>", parse_mode="HTML")

@bot.message_handler(commands=['referrals'])
def referrals(msg):
    link = f"https://t.me/{bot.get_me().username}?start={msg.from_user.id}"
    bot.send_message(msg.chat.id, f"🤝 <b>نظام الإحالة</b>\n\nشارك هذا الرابط مع أصدقائك واربح 10% من أرباحهم:\n<code>{link}</code>", parse_mode="HTML")

@bot.message_handler(commands=['setaddress'])
def setaddress(msg):
    bot.send_message(msg.chat.id, "📮 <b>تغيير عنوان المحفظة</b>\n\nالرجاء إرسال عنوان محفظة LTC صالح الآن.")

@bot.message_handler(func=lambda m: True)
def save_address(msg):
    user = get_user(msg)
    if msg.text.startswith("L") or msg.text.startswith("M") or msg.text.startswith("3"):
        user['address'] = msg.text
        bot.send_message(msg.chat.id, f"✅ <b>تم حفظ عنوان المحفظة بنجاح</b>\n\n<code>{msg.text}</code>", parse_mode="HTML")
    else:
        bot.send_message(msg.chat.id, "❌ <b>عنوان LTC غير صالح</b>\nيجب أن يبدأ بـ L أو M أو 3")

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
