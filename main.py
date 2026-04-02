import telebot
from telebot import types
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import threading
import os

app = Flask(__name__)
CORS(app)

# ТВОЙ ТОКЕН УЖЕ ЗДЕСЬ
TOKEN = "8685483938:AAHCYckrpVxFOfjGbnq0W1g3FmpA0ct8jJI"
bot = telebot.TeleBot(TOKEN)

# Настройки и база данных пользователей (в памяти)
config = {
    "welcome": "Привет! Я бот Urban Clash. Пришли ссылку на видео, и я скачаю его без водяных знаков! 🚀",
    "users": set() 
}

# --- ЛОГИКА СКАЧИВАНИЯ ---
def download_video(url):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'outtmpl': 'video.mp4',
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)
        return 'video.mp4'

# --- БОТ ---
@bot.message_handler(commands=['start'])
def start(message):
    config["users"].add(message.chat.id)
    bot.send_message(message.chat.id, config["welcome"])

@bot.message_handler(func=lambda m: True)
def handle_link(message):
    url = message.text
    if "tiktok.com" in url or "youtu" in url or "pin.it" in url:
        msg = bot.send_message(message.chat.id, "⏳ Начинаю загрузку без водяных знаков...")
        try:
            file_path = download_video(url)
            with open(file_path, 'rb') as v:
                bot.send_video(message.chat.id, v)
            os.remove(file_path)
            bot.delete_message(message.chat.id, msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ Ошибка загрузки. Проверь ссылку.", message.chat.id, msg.message_id)

# --- АДМИНКА (API для рассылки) ---
@app.route('/api/admin/promo', methods=['POST'])
def send_promo():
    data = request.json
    text = data.get('text')
    photo_url = data.get('photo')
    sticker_id = data.get('sticker') # ID премиум или обычного стикера
    buttons_raw = data.get('buttons', [])
    
    markup = types.InlineKeyboardMarkup()
    for b in buttons_raw:
        if "|" in b:
            name, link = b.split("|")
            markup.add(types.InlineKeyboardButton(text=name.strip(), url=link.strip()))

    count = 0
    for user_id in list(config["users"]):
        try:
            # 1. Сначала шлем стикер, если он есть
            if sticker_id:
                bot.send_sticker(user_id, sticker_id)
            
            # 2. Потом фото с текстом или просто текст
            if photo_url:
                bot.send_photo(user_id, photo_url, caption=text, reply_markup=markup, parse_mode="HTML")
            else:
                bot.send_message(user_id, text, reply_markup=markup, parse_mode="HTML")
            count += 1
        except: continue
    
    return jsonify({"success": True, "sent": count})

def run_bot():
    print("Бот Urban Clash запущен!")
    bot.polling(none_stop=True)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
