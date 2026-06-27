import telebot
from telebot import types
import requests

TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU"
FAUCETPAY_API = "حط_API_KEY_تاعك_هنا"
MIN_WITHDRAW = 0.001
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
def start(msg): show_menu(msg.chat.id, msg.from_user.first_name)

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
        msg = bot.send_message(msg.chat.id, "📮 <b>ضع إيميل FaucetPay للسحب</b>\n\n<b>مثال:</b> <code>you@gmail.com</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_withdraw_email)
        return
    show_withdraw_menu(msg)

def show_withdraw_menu(msg):
    user = get_user(msg)
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(f"سحب الكل: {user['balance']:.5f}", callback_data="withdraw_all"),
        types.InlineKeyboardButton("الحد الأدنى", callback_data=f"withdraw_{MIN_WITHDRAW}"),
        types.InlineKeyboardButton("رجوع", callback_data="back_menu")
    )
    bot.send_message(msg.chat.id, f"💵 <b>اختر المبلغ للسحب</b>\n\n<b>رصيدك:</b> <code>{user['balance']:.5f} LTC</code>\n<b>الحد الأدنى:</b> <code>{MIN_WITHDRAW} LTC</code>", reply_markup=keyboard, parse_mode="HTML")

def process_withdraw_email(msg):
    user = get_user(msg)
    if "@" in msg.text:
        user['faucetpay'] = msg.text
        bot.send_message(msg.chat.id, f"✅ <b>تم حفظ حسابك بنجاح</b>\n<code>{msg.text}</code>", parse_mode="HTML")
        show_withdraw_menu(msg) # نطلعو قائمة السحب طول
    else:
        bot.send_message(msg.chat.id, "❌ <b>ايميل غير صالح</b>. عاود ارسل ايميل FaucetPay صحيح.")

@bot.message_handler(commands=['setaddress'])
def setaddress(msg):
    msg = bot.send_message(msg.chat.id, "📮 <b>ضع إيميل FaucetPay الجديد</b>\n\n<b>مثال:</b> <code>you@gmail.com</code>", parse_mode="HTML")
    bot.register_next_step_handler(msg, save_address)

def save_address(msg):
    user = get_user(msg)
    if "@" in msg.text:
        user['faucetpay'] = msg.text
        bot.send_message(msg.chat.id, f"✅ <b>تم تغيير الحساب بنجاح</b>\n<b>ايميلك الجديد:</b> <code>{msg.text}</code>", parse_mode="HTML")
    else:
        bot.send_message(msg.chat.id, "❌ <b>ايميل غير صالح</b>", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "claim": claim(call.message)
    elif call.data == "balance": balance(call.message)
    elif call.data == "withdraw": withdraw(call.message)
    elif call.data == "top": top(call.message)
    elif call.data == "referrals": referrals(call.message)
    elif call.data == "setaddress": setaddress(call.message)
    elif call.data == "back_menu": start(call.message)
    elif call.data.startswith("withdraw_"):
        amount = float(call.data.split("_")[1]) if call.data!= "withdraw_all" else get_user(call.message)['balance']
        process_withdraw(call.message, amount)
    bot.answer_callback_query(call.id)

def process_withdraw(msg, amount):
    user = get_user(msg)
    if amount < MIN_WITHDRAW:
        return bot.send_message(msg.chat.id, f"❌ <b>رصيدك غير كافي</b>\nالحد الأدنى: <code>{MIN_WITHDRAW} LTC</code>", parse_mode="HTML")
    if user['balance'] < amount:
        return bot.send_message(msg.chat.id, f"❌ <b>رصيدك غير كافي</b>\nرصيدك: <code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

    res = send_fp_ltc(user['faucetpay'], amount)
    if res.get("status") == 200:
        user['balance'] -= amount
        bot.send_message(msg.chat.id, f"✅ <b>تم السحب بنجاح</b>\nتم تحويل <code>{amount:.5f} LTC</code>", parse_mode="HTML")
    else:
        bot.send_message(msg.chat.id, f"❌ <b>خطأ في السحب:</b> {res.get('message')}")

def balance(msg): bot.send_message(msg.chat.id, f"💳 <b>رصيدك:</b> <code>{get_user(msg)['balance']:.5f} LTC</code>", parse_mode="HTML")
def top(msg): bot.send_message(msg.chat.id, "🏅 <b>المتصدرين</b>\n1. Adam - 0.50000\n2. انت - 0.00000", parse_mode="HTML")
def referrals(msg): link = f"https://t.me/{bot.get_me().username}?start={msg.from_user.id}"; bot.send_message(msg.chat.id, f"🤝 <b>رابطك:</b>\n<code>{link}</code>", parse_mode="HTML")

if __name__ == "__main__":
    bot.polling(none_stop=True)
