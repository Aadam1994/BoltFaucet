import telebot
from telebot import types
import requests
import sqlite3

TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU"
FAUCETPAY_API = "حط_API_KEY_تاعك_هنا"
MIN_WITHDRAW = 0.001
bot = telebot.TeleBot(TOKEN)

user_states = {} # هذا برك اللي يتحكم في الحالة

conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL, faucetpay TEXT)''')
conn.commit()

def get_user(uid):
    c.execute("SELECT balance, faucetpay FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    if row: return {"user_id": uid, "balance": row[0], "faucetpay": row[1]}
    c.execute("INSERT INTO users VALUES (?,?,?)", (uid, 0.0, "غير محدد"))
    conn.commit()
    return {"user_id": uid, "balance": 0.0, "faucetpay": "غير محدد"}

def save_email(user_id, email):
    c.execute("UPDATE users SET faucetpay=? WHERE user_id=?", (email, user_id))
    conn.commit()

def update_balance(user_id, new_balance):
    c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
    conn.commit()

def send_fp_ltc(to, amount):
    url = "https://faucetpay.io/api/v1/send"
    data = {"api_key": FAUCETPAY_API, "to": to, "amount": amount, "currency": "LTC"}
    return requests.post(url, data=data).json()

@bot.message_handler(commands=['start'])
def start(msg): show_menu(msg.chat.id, msg.from_user.first_name)

def show_menu(chat_id, name):
    user = get_user(chat_id)
    text = f"✨ <b>لوحة التحكم</b> ✨\n\n<b>▫️ الاسم:</b> {name}\n<b>▫️ الرصيد:</b> <code>{user['balance']:.5f} LTC</code>\n<b>▫️ حساب FaucetPay:</b> <code>{user['faucetpay']}</code>"
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton("🎥 مشاهدة الإعلانات", callback_data="claim"), types.InlineKeyboardButton("💳 عرض الرصيد", callback_data="balance"), types.InlineKeyboardButton("💵 طلب سحب", callback_data="withdraw"), types.InlineKeyboardButton("📮 تغيير الحساب", callback_data="setaddress"))
    bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")

@bot.message_handler(commands=['claim'])
def claim(msg):
    user = get_user(msg.from_user.id)
    new_balance = user['balance'] + 0.00001
    update_balance(user['user_id'], new_balance)
    bot.send_message(msg.chat.id, f"✅ <b>تم إضافة 0.00001 LTC</b>\nرصيدك: <code>{new_balance:.5f}</code>", parse_mode="HTML")

@bot.message_handler(commands=['withdraw'])
def withdraw(msg):
    uid = msg.from_user.id
    user = get_user(uid)
    if user['faucetpay'] == "غير محدد":
        user_states[uid] = 'waiting_email'
        bot.send_message(msg.chat.id, "📮 <b>ضع إيميل FaucetPay للسحب</b>\n\n<b>مثال:</b> <code>you@gmail.com</code>", parse_mode="HTML")
    else:
        user_states[uid] = 'waiting_amount'
        bot.send_message(msg.chat.id, f"💵 <b>ادخل مبلغ السحب</b>\n<b>رصيدك:</b> <code>{user['balance']:.5f} LTC</code>\n<b>الحد الأدنى:</b> <code>{MIN_WITHDRAW} LTC</code>\n<b>للحساب:</b> <code>{user['faucetpay']}</code>", parse_mode="HTML")

@bot.message_handler(commands=['setaddress'])
def setaddress(msg):
    uid = msg.from_user.id
    user_states[uid] = 'waiting_new_email'
    bot.send_message(msg.chat.id, "📮 <b>ضع إيميل FaucetPay الجديد</b>\nسيتم استبدال القديم أوتوماتيكيا.", parse_mode="HTML")

# اهم تعديل: نستعمل user_states مباشرة ماشي get_user
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) in ['waiting_email', 'waiting_new_email'])
def process_email(msg):
    uid = msg.from_user.id
    if "@" in msg.text and "." in msg.text:
        save_email(uid, msg.text)
        user_states[uid] = 'waiting_amount' # نبدلو الحالة طول للمبلغ
        bot.send_message(msg.chat.id, f"✅ <b>تم حفظ الإيميل بنجاح</b>\n<code>{msg.text}</code>\n\n💵 <b>ادخل مبلغ السحب</b>\n<b>الحد الأدنى:</b> <code>{MIN_WITHDRAW} LTC</code>", parse_mode="HTML")
    else:
        bot.send_message(msg.chat.id, "❌ <b>ايميل غير صالح</b>. عاود ارسل ايميل صحيح.")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'waiting_amount')
def handle_amount(msg):
    uid = msg.from_user.id
    user = get_user(uid)
    try:
        amount = float(msg.text)
        user_states.pop(uid, None) # نمسحو الحالة بعد ما نكملو

        if amount < MIN_WITHDRAW:
            return bot.send_message(msg.chat.id, f"❌ <b>المبلغ أقل من الحد الأدنى</b>\nالحد الأدنى: <code>{MIN_WITHDRAW} LTC</code>", parse_mode="HTML")
        if user['balance'] < amount:
            return bot.send_message(msg.chat.id, f"❌ <b>رصيدك غير كافي</b>\nرصيدك: <code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

        res = send_fp_ltc(user['faucetpay'], amount)
        if res.get("status") == 200:
            update_balance(uid, user['balance'] - amount)
            bot.send_message(msg.chat.id, f"✅ <b>تم طلب السحب بنجاح</b>\nتم ارسال <code>{amount:.5f} LTC</code> الى <code>{user['faucetpay']}</code>", parse_mode="HTML")
        else:
            bot.send_message(msg.chat.id, f"❌ <b>خطأ في السحب:</b> {res.get('message')}")

    except ValueError:
        bot.send_message(msg.chat.id, "❌ <b>ارسل رقم صحيح</b>. مثال: 0.001", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "claim": claim(call.message)
    elif call.data == "balance": balance(call.message)
    elif call.data == "withdraw": withdraw(call.message)
    elif call.data == "setaddress": setaddress(call.message)
    bot.answer_callback_query(call.id)

def balance(msg): user = get_user(msg.from_user.id); bot.send_message(msg.chat.id, f"💳 <b>رصيدك:</b> <code>{user['balance']:.5f} LTC</code>", parse_mode="HTML")

if __name__ == "__main__":
    print("Bot is running...")
    bot.polling(none_stop=True, skip_pending=True)
