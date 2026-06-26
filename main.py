import telebot
import time

# حط التوكن تاع البوت هنا
TOKEN = "8917587862:AAH627Ik8bEj43TyIVAVkdTpefdacdfl3PU"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "مرحبا بك في صنبور BoltFaucet LTC 💧\nارسل /claim باش تاخذ لايتكوين")

@bot.message_handler(commands=['claim'])
def claim(msg):
    bot.reply_to(msg, "تم، راح توصلك LTC قريبا")

def main():
    print("Hello from BoltFaucet")
    # هذا هو اللي يخلي البوت شاعل 24/24
    bot.infinity_polling(skip_pending=True, timeout=20)

if __name__ == "__main__":
    main()
