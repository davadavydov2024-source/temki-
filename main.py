import logging
import asyncio
import os
import aiohttp
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, URLInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('BOT_TOKEN')
RENDER_EXTERNAL_URL = "https://temki-1.onrender.com" 
ADMIN_ID = 7040863301

data_store = {
    "greeting": (
        "<b>Привет! Я бот для скачивания медиа.</b> 📥\n\n"
        "Отправь мне ссылку на видео из:\n"
        "• <b>TikTok</b>\n"
        "• <b>Pinterest</b>\n"
        "• <b>Likee</b>\n\n"
        "<i>Просто пришли ссылку, и я отправлю видео файлом!</i>"
    ),
    "users": set()
}

class AdminStates(StatesGroup):
    waiting_for_ad_text = State()
    waiting_for_new_greeting = State()

logging.basicConfig(level=logging.INFO)

if not API_TOKEN:
    logging.error("ОШИБКА: BOT_TOKEN не найден!")
    exit(1)

# ИСПРАВЛЕННАЯ ИНИЦИАЛИЗАЦИЯ (для aiogram 3.7.0+)
bot = Bot(
    token=API_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# --- СКАЧИВАНИЕ ---
def download_video(url):
    ydl_opts = {'format': 'best', 'quiet': True, 'no_warnings': True, 'cachedir': False}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('url')
    except Exception as e:
        logging.error(f"Download error: {e}")
        return None

# --- ВЕБ-СЕРВЕР И САМОПИНГ ---
async def handle(request):
    return web.Response(text="Urban Clash is Alive!")

async def self_ping():
    await asyncio.sleep(20)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(RENDER_EXTERNAL_URL) as resp:
                    logging.info(f"Self-ping: {resp.status}")
        except: pass
        await asyncio.sleep(300)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080)))
    await site.start()

# --- ХЕНДЛЕРЫ ---
@dp.message(F.text.regexp(r'(tiktok\.com|pinterest\.com|pin\.it|likee\.video)'))
async def handle_video_link(message: types.Message):
    wait_msg = await message.answer("⏳ <b>Обрабатываю ссылку...</b>")
    video_url = download_video(message.text)
    if video_url:
        try:
            await message.answer_video(URLInputFile(video_url), caption="✅ <b>Готово!</b>")
            await wait_msg.delete()
        except: await wait_msg.edit_text("❌ Ошибка отправки.")
    else: await wait_msg.edit_text("❌ Видео не найдено.")

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    data_store["users"].add(message.from_user.id)
    await message.answer(data_store["greeting"])

@dp.message(Command("adminARTEMK101"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="👋 Смена приветствия", callback_data="admin_change_greet")]
        ])
        await message.answer("🛠 <b>Админка</b>", reply_markup=kb)

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Текст рассылки:")
    await state.set_state(AdminStates.waiting_for_ad_text)
    await callback.answer()

@dp.message(AdminStates.waiting_for_ad_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    for u_id in data_store["users"]:
        try: await bot.send_message(u_id, message.text)
        except: pass
    await message.answer("✅ Отправлено!")
    await state.clear()

async def main():
    asyncio.create_task(start_web_server())
    asyncio.create_task(self_ping())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
