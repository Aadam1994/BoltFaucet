import telebot
from telebot import types
TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU"
bot = telebot.TeleBot(TOKEN)
user_data = {}
def get_user(msg):
    uid = msg.from_user.id
    if uid not in user_data: user_data[uid] = {"balance": 0.0, "address": "غير مضبوط"}
    return user_data[uid]
@bot.message_handler(commands=['start'])
def start(msg):
    user = get_user(msg)
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton("🎬 مشاهدة", callback_data="claim"), types.InlineKeyboardButton("💰 رصيدي", callback_data="balance"))
    bot.send_message(msg.chat.id, f"💎 مرحبا {msg.from_user.first_name}\nرصيدك: {user['balance']} LTC", reply_markup=keyboard)
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "claim": bot.send_message(call.message.chat.id, "✅ تم! +0.00001 LTC")
    if call.data == "balance": bot.send_message(call.message.chat.id, "💰 رصيدك: 0.0 LTC")
    bot.answer_callback_query(call.id)
bot.polling(none_stop=True)
