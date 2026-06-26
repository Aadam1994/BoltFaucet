import telebot
from telebot import types
import time

# حط التوكن تاعك هنا
TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTr"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(msg):
    name = msg.from_user.first_name
    balance = 0.00 # هنا تبدلها كي تربط قاعدة البيانات
    
    text = f"""💎 مرحبا {name} | Welcome {name}

أنت الآن في بوت Ltc Earn Faucet
رصيدك الحالي: {balance} LTC
السحب يبدأ من: 0.001 LTC
"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎬 مشاهدة إعلانات", callback_data="claim")
    btn2 = types.InlineKeyboardButton("💰 رصيدي", callback_data="balance")
    btn3 = types.InlineKeyboardButton("👥 دعوة أصدقاء", callback_data="ref")
    btn4 = types.InlineKeyboardButton("💸 سحب", callback_data="withdraw")
    keyboard.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(msg.chat.id, text, reply_markup=keyboard, parse_mode="Markdown")

@bot.message_handler(commands=['claim'])
def claim(msg):
    bot.reply_to(msg, "✅ تم، راك ربحت LTC. رصيدك تحدث.")

def main():
    print("Hello from BoltFaucet")
    # هذا يخلي البوت شاعل 24/24
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    main()
