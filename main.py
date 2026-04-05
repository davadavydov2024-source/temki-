import os
import asyncio
import logging
import sqlite3
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import yt_dlp

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN", "").strip().replace(" ", "")
ADMIN_ID = 7040863301
PORT = int(os.getenv("PORT", 8080))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect("bot_manager.db")
    cur = conn.cursor()
    cur.execute(query, params)
    res = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

# --- УЛУЧШЕННАЯ ТЕХНИКА СКАЧИВАНИЯ ---
def download_video(url):
    random_filename = f"dl_{int(time.time())}.mp4"
    
    ydl_opts = {
        # Формат: лучшее видео с аудио, совместимое с TG (mp4)
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': random_filename,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        # Эмуляция реального браузера (критично для TikTok и Likee)
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
        'add_header': [
            'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language:ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'
        ],
        # Автоматический подбор cookies (помогает обходить капчи)
        'http_chunk_size': 1048576,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Получаем реальное имя файла, которое сохранил yt-dlp
        return ydl.prepare_filename(info)

# --- ОБРАБОТКА ССЫЛОК ---
@dp.message(F.text.regexp(r'(https?://[^\s]+)'))
async def handle_dl(message: types.Message):
    url = message.text.strip()
    wait_msg = await message.answer("🏁 *Начинаю загрузку...* \nЭто может занять до 30 секунд.", parse_mode="Markdown")
    
    try:
        # Запускаем в отдельном потоке
        path = await asyncio.to_thread(download_video, url)
        
        if os.path.exists(path):
            video = FSInputFile(path)
            await message.reply_video(video=video, caption="Готово! Save Lyneok Videos 🏁")
            os.remove(path) # Сразу удаляем, чтобы не забивать Render
            await wait_msg.delete()
        else:
            raise Exception("File not found")

    except Exception as e:
        logging.error(f"Download error: {e}")
        await wait_msg.edit_text("❌ *Ошибка!* \nНе удалось скачать видео. Попробуйте другую ссылку или проверьте, не удалено ли видео.")

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет! Я **Save Lyneok Videos** 🏁\nПришли мне ссылку из TikTok, Likee или Pinterest!")

# --- АВТО-ПРОБУЖДЕНИЕ ---
async def self_ping():
    while True:
        await asyncio.sleep(600)
        if RENDER_URL:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(RENDER_URL) as r: pass
            except: pass

async def main():
    # Web server для Render
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    
    asyncio.create_task(self_ping())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
