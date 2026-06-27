import telebot
from telebot import types
import requests

TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU"
FAUCETPAY_API = "حط_API_KEY_تاعك_هنا"
bot = telebot.TeleBot(TOKEN)

user_data = {}

def get_user(msg):
    uid = msg.from_user.id
    if uid not in user_data:
        user_data[uid] = {"balance": 0.0, "faucetpay": "غير محدد"}
    return user_data[uid]

def send_fp_ltc(to, amount):
    url = "https://faucetpay.io/api/v1/send"
    data = {"api_key": FAUCETPAY_API, "to": to, "amount": amount, "currency": "LTC"}
    r = requests.post(url, data=data)
    return r.json()

@bot.message_handler(commands=['start'])
def start(msg):
    show_menu(msg.chat.id, msg.from_user.first_name)

def show_menu(chat_id, name):
    user = get_user(type('obj', (object,), {'from_user': type('obj', (object,), {'id': chat_id})}))
    text = f"""✨ <b>لوحة التحكم</b> ✨

<b>▫️ الاسم:</b> {name}
<b>▫️ الرصيد:</b> <code>{user['balance']:.5f} LTC</code>
<b>▫️ حساب FaucetPay:</b> <code>{user['faucetpay']}</code>
"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🎥 مشاهدة الإعلانات", callback_data="claim"),
        types.InlineKeyboardButton("💳 عرض الرصيد", callback_data="balance"),
        types.InlineKeyboardButton("💵 طلب سحب", callback_data="withdraw"),
        types.InlineKeyboardButton("🏅 المتصدرين", callback_data="top"),
        types.InlineKeyboardButton("🤝 الإحالة", callback_data="referrals"),
        types.InlineKeyboardButton("📮 تغيير الحساب", callback_data="setaddress")
    )
    bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")

@bot.message_handler(commands=['claim'])
def claim(msg):
    user = get_user(msg)
    user['balance'] += 0.00001
    bot.send_message(msg.chat.id, f"✅ <b>تم إضافة 0.00001 LTC</b>\nرصيدك: <code>{user['balance']:.5f}</code>", parse_mode="HTML")

@bot.message_handler(commands=['withdraw'])
def withdraw(msg):
    user = get_user(msg)
    if user['faucetpay'] == "غير محدد":
        return bot.send_message(msg.chat.id, "❌ <b>حط ايميل FaucetPay تاعك اول</b> من زر تغيير الحساب", parse_mode="HTML")
    if user['balance'] >= 0.001:
        res = send_fp_ltc(user['faucetpay'], user['balance'])
        if res.get("status") == 200:
            bot.send_message(msg.chat.id, f"✅ <b>تم السحب بنجاح</b>\nتم تحويل <code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")
            user['balance'] = 0
        else:
            bot.send_message(msg.chat.id, f"❌ <b>خطأ في السحب:</b> {res.get('message')}")
    else:
        bot.send_message(msg.chat.id, f"❌ <b>الحد الأدنى 0.001 LTC</b>\nرصيدك: <code>{user['balance']:.5f}</code>", parse_mode="HTML")

@bot.message_handler(commands=['setaddress'])
def setaddress(msg):
    bot.send_message(msg.chat.id, "📮 <b>ضع ايميل FaucetPay الخاص بك</b>\n\nمثال: you@gmail.com\nسيتم السحب لهذا الحساب مباشرة.", parse_mode="HTML")

@bot.message_handler(func=lambda m: True)
def save_address(msg):
    user = get_user(msg)
    if "@" in msg.text:
        user['faucetpay'] = msg.text
        bot.send_message(msg.chat.id, f"✅ <b>تم حفظ حساب FaucetPay</b>\n<code>{msg.text}</code>", parse_mode="HTML")
    else:
        bot.send_message(msg.chat.id, "❌ <b>هذا ليس ايميل صالح</b>", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "claim": claim(call.message)
    elif call.data == "balance": balance(call.message)
    elif call.data == "withdraw": withdraw(call.message)
    elif call.data == "top": top(call.message)
    elif call.data == "referrals": referrals(call.message)
    elif call.data == "setaddress": setaddress(call.message)
    bot.answer_callback_query(call.id)

def balance(msg): bot.send_message(msg.chat.id, f"💳 <b>رصيدك:</b> <code>{get_user(msg)['balance']:.5f} LTC</code>", parse_mode="HTML")
def top(msg): bot.send_message(msg.chat.id, "🏅 <b>المتصدرين</b>\n1. Adam - 0.50000\n2. انت - 0.00000", parse_mode="HTML")
def referrals(msg): bot.send_message(msg.chat.id, f"🤝 <b>رابطك:</b>\n<code>https://t.me/{bot.get_me().username}?start={msg.from_user.id}</code>", parse_mode="HTML")

if __name__ == "__main__":
    bot.polling(none_stop=True)
