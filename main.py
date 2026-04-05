import os
import asyncio
import logging
import sqlite3
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
import yt_dlp

# --- СОСТОЯНИЯ ДЛЯ АДМИНКИ ---
class AdminStates(StatesGroup):
    wait_broadcast = State()
    wait_new_text = State()
    wait_new_channel = State()
    wait_ban_id = State()

# --- КОНФИГУРАЦИЯ ---
raw_token = os.getenv("BOT_TOKEN", "").strip()
TOKEN = raw_token.replace(" ", "") # Убираем пробелы принудительно
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

def init_db():
    db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active')")
    db_query("CREATE TABLE IF NOT EXISTS channels (url TEXT)")
    db_query("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    db_query("INSERT OR IGNORE INTO settings VALUES ('start_text', 'Привет! Отправь ссылку на видео из TikTok, Likee или Pinterest 🏁')")

init_db()

# --- ТЕХНИКА СКАЧИВАНИЯ ---
def download_video(url):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'video_{int(time.time())}.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0 Safari/537.36'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# --- ГЛАВНОЕ АДМИН-МЕНЮ ---
def get_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📝 Сменить приветствие", callback_data="adm_set_text")],
        [InlineKeyboardButton(text="🔗 Добавить канал", callback_data="adm_add_ch")],
        [InlineKeyboardButton(text="🚫 Забанить юзера", callback_data="adm_ban")],
        [InlineKeyboardButton(text="❌ Сбросить каналы", callback_data="adm_clear_ch")]
    ])

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_start(message: types.Message):
    await message.answer("🛠 **Панель управления Save Lyneok Videos**", reply_markup=get_admin_kb())

# --- ОБРАБОТКА КНОПОК АДМИНКИ ---
@dp.callback_query(F.data == "adm_broadcast", F.from_user.id == ADMIN_ID)
async def broadcast_step(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.wait_broadcast)
    await call.message.answer("Введите текст для рассылки всем пользователям:")
    await call.answer()

@dp.message(AdminStates.wait_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    users = db_query("SELECT id FROM users", fetch=True)
    count = 0
    for u in users:
        try:
            await bot.send_message(u[0], message.text)
            count += 1
        except: pass
    await message.answer(f"✅ Рассылка завершена! Получили {count} человек.")
    await state.clear()

@dp.callback_query(F.data == "adm_set_text", F.from_user.id == ADMIN_ID)
async def change_text_step(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.wait_new_text)
    await call.message.answer("Введите новый текст приветствия (/start):")
    await call.answer()

@dp.message(AdminStates.wait_new_text)
async def save_text(message: types.Message, state: FSMContext):
    db_query("UPDATE settings SET value = ? WHERE key = 'start_text'", (message.text,))
    await message.answer("✅ Текст приветствия обновлен!")
    await state.clear()

@dp.callback_query(F.data == "adm_add_ch", F.from_user.id == ADMIN_ID)
async def add_ch_step(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.wait_new_channel)
    await call.message.answer("Отправьте ссылку на канал (https://t.me/...)")
    await call.answer()

@dp.message(AdminStates.wait_new_channel)
async def save_ch(message: types.Message, state: FSMContext):
    db_query("INSERT INTO channels (url) VALUES (?)", (message.text,))
    await message.answer("✅ Канал добавлен в список ОП!")
    await state.clear()

@dp.callback_query(F.data == "adm_clear_ch", F.from_user.id == ADMIN_ID)
async def clear_ch(call: types.CallbackQuery):
    db_query("DELETE FROM channels")
    await call.message.answer("✅ Список обязательных каналов очищен.")
    await call.answer()

# --- ЛОГИКА СКАЧИВАНИЯ ДЛЯ ЮЗЕРОВ ---
@dp.message(F.text.contains("http"))
async def handle_dl(message: types.Message):
    user = db_query("SELECT status FROM users WHERE id = ?", (message.from_user.id,), fetch=True)
    if user and user[0][0] == 'banned':
        return await message.answer("🚫 Вы заблокированы админом.")
    
    db_query("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    
    wait = await message.answer("🚀 *Загружаю видео...*", parse_mode="Markdown")
    try:
        path = await asyncio.to_thread(download_video, message.text.strip())
        await message.reply_video(video=FSInputFile(path), caption="Готово! 🏁")
        os.remove(path)
        await wait.delete()
    except Exception as e:
        logging.error(e)
        await wait.edit_text("❌ Ошибка! Не удалось скачать видео. Проверьте ссылку.")

@dp.message(Command("start"))
async def start(message: types.Message):
    db_query("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    txt = db_query("SELECT value FROM settings WHERE key = 'start_text'", fetch=True)[0][0]
    
    channels = db_query("SELECT url FROM channels", fetch=True)
    kb = None
    if channels:
        btns = [[InlineKeyboardButton(text="📢 Подписаться", url=c[0])] for c in channels]
        kb = InlineKeyboardMarkup(inline_keyboard=btns)
    
    await message.answer(txt, reply_markup=kb)

# --- ПРОБУЖДЕНИЕ ---
async def self_ping():
    while True:
        await asyncio.sleep(600)
        if RENDER_URL:
            try:
                async with asyncio.timeout(10):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(RENDER_URL) as r: pass
            except: pass

async def main():
    # Запуск сервера для Render
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
