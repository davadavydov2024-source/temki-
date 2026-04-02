import telebot
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import threading
import os

app = Flask(__name__)
CORS(app)

# Хранилище настроек
config = {
    "token": "YOUR_TOKEN",
    "welcome": "Привет! Я бот Easy Downloader. Пришли ссылку!",
    "channels": [] # Список до 10 каналов
}

bot = telebot.TeleBot(config["token"])

@app.route('/api/download', methods=['POST'])
def download():
    url = request.json.get('url')
    try:
        with yt_dlp.YoutubeDL({'format': 'best', 'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({"success": True, "link": info['url']})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin', methods=['POST'])
def admin_update():
    global config, bot
    data = request.json
    config["token"] = data.get("token", config["token"])
    config["welcome"] = data.get("welcome", config["welcome"])
    config["channels"] = data.get("channels", [])
    
    # Переподключаем бота, если токен новый
    bot = telebot.TeleBot(config["token"])
    return jsonify({"status": "updated"})

# Логика бота с проверкой подписки на все 10 каналов
def check_sub(user_id):
    for channel in config["channels"]:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status == 'left': return False
        except: continue
    return True

@bot.message_handler(commands=['start'])
def welcome(message):
    if not check_sub(message.from_user.id):
        channels_str = "\n".join(config["channels"])
        bot.send_message(message.chat.id, f"❌ Подпишись на каналы, чтобы пользоваться ботом:\n{channels_str}")
    else:
        bot.send_message(message.chat.id, config["welcome"])

def start_bot():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    threading.Thread(target=start_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
