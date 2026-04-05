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
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = 7040863301  # Твой ID
PORT = int(os.getenv("PORT", 8080))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "") # Твоя ссылка .onrender.com

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect("bot_data.db")
    cur = conn.cursor()
    cur.execute(query, params)
    res = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

def init_db():
    db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active')")
    db_query("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT)")
    db_query("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    # Начальное приветствие
    db_query("INSERT OR IGNORE INTO settings VALUES ('start_text', 'Привет! Отправь ссылку на видео 🏁')")

init_db()

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_sub(user_id):
    channels = db_query("SELECT url FROM channels", fetch=True)
    if not channels: return True
    # Здесь упрощенная логика (просто показываем кнопки, т.к. проверка требует прав админа в каналах)
    return True 

# --- АВТО-ПРОБУЖДЕНИЕ ---
async def self_ping():
    while True:
        await asyncio.sleep(600)
        if RENDER_URL:
            try:
                async with asyncio.timeout(10):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(RENDER_URL) as r:
                            logging.info(f"Ping: {r.status}")
            except: pass

# --- ТЕХНИКА СКАЧИВАНИЯ ---
def download_vid(url):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'dl_{int(time.time())}.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0 Safari/537.36'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# --- АДМИНКА ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_main(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="🔗 Каналы (ОП)", callback_data="adm_channels")],
        [InlineKeyboardButton(text="📝 Текст приветствия", callback_data="adm_text")],
        [InlineKeyboardButton(text="🚫 Блок юзера", callback_data="adm_block")]
    ])
    await message.answer("🛠 Панель управления Save Lyneok Videos 🏁", reply_markup=kb)

@dp.callback_query(F.data == "adm_channels")
async def adm_ch(call: types.CallbackQuery):
    channels = db_query("SELECT id, url FROM channels", fetch=True)
    text = "Список каналов для подписки:\n" + "\n".join([f"{c[0]}. {c[1]}" for c in channels])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_ch")],
        [InlineKeyboardButton(text="🗑 Удалить всё", callback_data="del_ch_all")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- ОБРАБОТКА ССЫЛОК ---
@dp.message(F.text.contains("http"))
async def handle_links(message: types.Message):
    user = db_query("SELECT status FROM users WHERE id = ?", (message.from_user.id,), fetch=True)
    if user and user[0][0] == 'banned':
        return await message.answer("❌ Вы заблокированы.")
    
    db_query("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    
    status_msg = await message.answer("⏳ Скачиваю видео...")
    try:
        path = await asyncio.to_thread(download_vid, message.text.strip())
        await message.reply_video(video=FSInputFile(path), caption="Готово! 🏁")
        os.remove(path)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка. Ссылка не поддерживается или видео скрыто.")

@dp.message(Command("start"))
async def start(message: types.Message):
    db_query("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    txt = db_query("SELECT value FROM settings WHERE key = 'start_text'", fetch=True)[0][0]
    
    channels = db_query("SELECT url FROM channels", fetch=True)
    kb = None
    if channels:
        btns = [[InlineKeyboardButton(text="Подписаться", url=c[0])] for c in channels]
        kb = InlineKeyboardMarkup(inline_keyboard=btns)
        
    await message.answer(txt, reply_markup=kb)

# --- ЗАПУСК ---
async def handle_web(request): return web.Response(text="OK")

async def main():
    # Web server
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    
    asyncio.create_task(self_ping())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
