import telebot
from telebot import types

TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU" 
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(msg):
    name = msg.from_user.first_name
    balance = 0.00
    
    text = f"""💎 مرحبا {name} | Welcome {name}

أنت الآن في بوت Ltc Earn Faucet
رصيدك الحالي: {balance} LTC
السحب يبدأ من: 0.001 LTC
"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎬 مشاهدة إعلانات", callback_data="claim")
    btn2 = types.InlineKeyboardButton("💰 رصيدي", callback_data="balance")
    keyboard.add(btn1, btn2)
    
    bot.send_message(msg.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "claim":
        bot.answer_callback_query(call.id, "✅ تم ربحت LTC")

def main():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    main()
