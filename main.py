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
        user_data[uid] = {"balance": 0.0, "faucetpay": "غير محدد", "state": None}
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
    # 1. اذا معندوش ايميل، نطلبو. اذا عندو نطلع المنيو طول
    if user['faucetpay'] == "غير محدد":
        user['state'] = 'waiting_email'
        msg = bot.send_message(msg.chat.id, "📮 <b>ضع إيميل FaucetPay للسحب</b>\n\n<b>مثال:</b> <code>you@gmail.com</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_email)
    else:
        show_withdraw_menu(msg)

def show_withdraw_menu(msg):
    user = get_user(msg)
    user['state'] = 'waiting_amount'
    text = f"""💵 <b>اختر المبلغ للسحب</b>

<b>رصيدك:</b> <code>{user['balance']:.5f} LTC</code>
<b>الحد الأدنى:</b> <code>{MIN_WITHDRAW} LTC</code>

<b>ملاحظة:</b> السحب يرسل تلقائي على الساعة 00:00 (GMT+1)
"""
    bot.send_message(msg.chat.id, text, parse_mode="HTML")

def process_email(msg):
    user = get_user(msg)
    if "@" in msg.text:
        user['faucetpay'] = msg.text
        bot.send_message(msg.chat.id, f"✅ <b>تم حفظ حسابك بنجاح</b>\n<code>{msg.text}</code>", parse_mode="HTML")
        show_withdraw_menu(msg) # نطلعو المنيو مرة وحدة برك
    else:
        bot.send_message(msg.chat.id, "❌ <b>ايميل غير صالح</b>. عاود ارسل ايميل صحيح.")
        user['state'] = 'waiting_email'
        bot.register_next_step_handler(msg, process_email)

@bot.message_handler(commands=['setaddress'])
def setaddress(msg):
    user = get_user(msg)
    user['state'] = 'waiting_new_email'
    msg = bot.send_message(msg.chat.id, "📮 <b>ضع إيميل FaucetPay الجديد</b>\n\n<b>مثال:</b> <code>you@gmail.com</code>", parse_mode="HTML")
    bot.register_next_step_handler(msg, save_address)

def save_address(msg):
    user = get_user(msg)
    if "@" in msg.text:
        user['faucetpay'] = msg.text
        bot.send_message(msg.chat.id, f"✅ <b>تم تغيير الحساب بنجاح</b>\n<b>ايميلك الجديد:</b> <code>{msg.text}</code>", parse_mode="HTML")
    else:
        bot.send_message(msg.chat.id, "❌ <b>ايميل غير صالح</b>", parse_mode="HTML")
    user['state'] = None

@bot.message_handler(func=lambda m: True)
def handle_text(msg):
    user = get_user(msg)

    if user.get('state') == 'waiting_amount':
        try:
            amount = float(msg.text)
            user['state'] = None
            process_withdraw(msg, amount)
        except ValueError:
            bot.send_message(msg.chat.id, "❌ <b>ارسل رقم صحيح</b>. مثال: 0.001", parse_mode="HTML")
    else:
        # اذا مكاش state، نتجاهلو الرسالة باش ما يعاودش
        pass

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "claim": claim(call.message)
    elif call.data == "balance": balance(call.message)
    elif call.data == "withdraw": withdraw(call.message)
    elif call.data == "top": top(call.message)
    elif call.data == "referrals": referrals(call.message)
    elif call.data == "setaddress": setaddress(call.message)
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
        bot.send_message(msg.chat.id, f"✅ <b>تم طلب السحب بنجاح</b>\nسيتم ارسال <code>{amount:.5f} LTC</code> على الساعة 00:00 (GMT+1)", parse_mode="HTML")
    else:
        bot.send_message(msg.chat.id, f"❌ <b>خطأ في السحب:</b> {res.get('message')}")

def balance(msg): bot.send_message(msg.chat.id, f"💳 <b>رصيدك:</b> <code>{get_user(msg)['balance']:.5f} LTC</code>", parse_mode="HTML")
def top(msg): bot.send_message(msg.chat.id, "🏅 <b>المتصدرين</b>\n1. Adam - 0.50000\n2. انت - 0.00000", parse_mode="HTML")
def referrals(msg): link = f"https://t.me/{bot.get_me().username}?start={msg.from_user.id}"; bot.send_message(msg.chat.id, f"🤝 <b>رابطك:</b>\n<code>{link}</code>", parse_mode="HTML")

if __name__ == "__main__":
    bot.polling(none_stop=True)
