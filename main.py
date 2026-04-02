import telebot
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import threading
import os

app = Flask(__name__)
CORS(app)

# Текущие настройки проекта
state = {
    "token": "ТВОЙ_ТОКЕН_ИЗ_BOTFATHER",
    "welcome": "Добро пожаловать в Easy Downloader! Пришли ссылку.",
    "channels": [] # Сюда прилетят до 10 каналов из админки
}

bot = telebot.TeleBot(state["token"])

# Функция проверки подписки на все указанные каналы
def check_subscriptions(user_id):
    if not state["channels"]: return True
    for ch in state["channels"]:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status == 'left': return False
        except: continue 
    return True

@app.route('/api/download', methods=['POST'])
def handle_dl():
    target_url = request.json.get('url')
    # Настройки yt-dlp для чистого скачивания без в.з.
    opts = {'format': 'best', 'quiet': True, 'noplaylist': True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            return jsonify({"success": True, "link": info['url']})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin', methods=['POST'])
def handle_admin():
    global state, bot
    data = request.json
    if data.get("token"):
        state["token"] = data["token"]
        bot = telebot.TeleBot(state["token"]) # Пересоздаем бота с новым токеном
    state["welcome"] = data.get("welcome", state["welcome"])
    state["channels"] = data.get("channels", [])
    return jsonify({"status": "success"})

# Логика Telegram бота
@bot.message_handler(commands=['start'])
def bot_start(message):
    if check_subscriptions(message.from_user.id):
        bot.send_message(message.chat.id, state["welcome"])
    else:
        msg = "❌ Ошибка доступа! Сначала подпишись на наши каналы:\n\n"
        for ch in state["channels"]:
            msg += f"🔗 {ch}\n"
        bot.send_message(message.chat.id, msg)

def run_bot_polling():
    print("Бот Urban Clash запущен...")
    bot.polling(none_stop=True)

if __name__ == '__main__':
    # Запуск бота в отдельном потоке, чтобы Flask не блокировался
    threading.Thread(target=run_bot_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
