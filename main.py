import telebot
from telebot import types
import requests
import sqlite3
from datetime import datetime

TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU" # حط التوكن تاعك
FAUCETPAY_API = "حط_API_KEY_تاعك_هنا"
MIN_WITHDRAW = 0.001
ADMIN_ID = 0 # حط ID تاعك هنا جيبو من @userinfobot
CHANNEL_LINK = "https://t.me/حط_يوزر_القناة_تاعك" # بدلها
bot = telebot.TeleBot(TOKEN)

user_states = {}

conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
# عدلت الجدول باش يزيد عمود التاريخ. اذا البوت عندك خدام، امسح users.db وعاود شغلو مرة وحدة
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL, faucetpay TEXT, last_claim TEXT)")
conn.commit()

def get_user(uid):
    c.execute("SELECT balance, faucetpay, last_claim FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    if row: return {"balance": row[0], "faucetpay": row[1], "last_claim": row[2]}
    c.execute("INSERT INTO users VALUES (?, 0.0, 'غير محدد', NULL)", (uid,))
    conn.commit()
    return {"balance": 0.0, "faucetpay": "غير محدد", "last_claim": None}

def save_email(uid, email):
    c.execute("UPDATE users SET faucetpay=? WHERE user_id=?", (email, uid)); conn.commit()

def update_balance(uid, new_balance):
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("UPDATE users SET balance=?, last_claim=? WHERE user_id=?", (new_balance, today, uid)); conn.commit()

@bot.message_handler(commands=['start'])
def start(msg):
    user = get_user(msg.from_user.id)
    text = f"✨ لوحة التحكم ✨\n\nالاسم: {msg.from_user.first_name}\nالرصيد: {user['balance']:.5f} LTC\nحساب FaucetPay: {user['faucetpay']}"

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("💳 عرض الرصيد", callback_data="balance"),
        types.InlineKeyboardButton("🎥 مشاهدة الاعلانات", callback_data="claim")
    )
    keyboard.add(
        types.InlineKeyboardButton("💵 طلب سحب", callback_data="withdraw"),
        types.InlineKeyboardButton("📮 تغيير الحساب", callback_data="setaddress")
    )
    # زر القناة الجديد
    keyboard.add(types.InlineKeyboardButton("📢 قناة الاخبار", url=CHANNEL_LINK))
    bot.send_message(msg.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.from_user.id
    if call.data == "claim":
        user = get_user(uid)
        new_balance = user['balance'] + 0.00001
        update_balance(uid, new_balance) # هنا يتسجل تاريخ اليوم
        bot.answer_callback_query(call.id, f"تم اضافة 0.00001 LTC")
        start(call.message)

    elif call.data == "balance":
        user = get_user(uid)
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"💳 رصيدك الحالي: {user['balance']:.5f} LTC")

    elif call.data == "withdraw":
        user = get_user(uid)
        if user['faucetpay'] == "غير محدد":
            user_states[uid] = 'waiting_email'
            bot.send_message(call.message.chat.id, "ضع ايميل FaucetPay للسحب:\nمثال: you@gmail.com")
        else:
            user_states[uid] = 'waiting_amount'
            bot.send_message(call.message.chat.id, f"ادخل مبلغ السحب:\nرصيدك: {user['balance']:.5f} LTC\nالحد الادنى: {MIN_WITHDRAW} LTC\nللحساب: {user['faucetpay']}")
        bot.answer_callback_query(call.id)

    elif call.data == "setaddress":
        user_states[uid] = 'waiting_new_email'
        bot.send_message(call.message.chat.id, "ضع إيميل FaucetPay الجديد")
        bot.answer_callback_query(call.id)

# امر الاحصائيات ليك برك
@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id!= ADMIN_ID:
        return

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM users WHERE last_claim=?", (today,))
    active_today = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users WHERE balance > 0")
    earners = c.fetchone()[0]

    bot.send_message(msg.chat.id, f"📊 احصائيات البوت:\n\n👥 الكلي: {total_users}\n✅ النشطين اليوم: {active_today}\n💰 اللي جمعو رصيد: {earners}")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) in ['waiting_email', 'waiting_new_email'])
def process_email(msg):
    uid = msg.from_user.id
    email = msg.text.strip()
    if "@" in email and "." in email:
        save_email(uid, email)
        user_states[uid] = 'waiting_amount'
        bot.send_message(msg.chat.id, f"تم حفظ الايميل بنجاح: {email}\n\nالان ادخل مبلغ السحب:")
    else:
        bot.send_message(msg.chat.id, "ايميل غير صالح. عاود ارسل ايميل صحيح.")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'waiting_amount')
def handle_amount(msg):
    uid = msg.from_user.id
    user = get_user(uid)
    try:
        amount = float(msg.text)
        user_states.pop(uid, None)

        if amount < MIN_WITHDRAW:
            return bot.send_message(msg.chat.id, f"المبلغ اقل من الحد الادنى. الحد الادنى هو {MIN_WITHDRAW} LTC")
        if user['balance'] < amount:
            return bot.send_message(msg.chat.id, f"رصيدك غير كافي. رصيدك هو {user['balance']:.5f} LTC")

        update_balance(uid, user['balance'] - amount)
        bot.send_message(msg.chat.id, f"تم طلب السحب بنجاح.\nتم ارسال {amount:.5f} LTC الى {user['faucetpay']}")
        start(msg)

    except ValueError:
        bot.send_message(msg.chat.id, "ارسل رقم صحيح. مثال: 0.001")

if __name__ == "__main__":
    print("البوت يعمل...")
    bot.infinity_polling()
