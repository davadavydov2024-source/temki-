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
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
RENDER_EXTERNAL_URL = "https://temki-jgp0.onrender.com" 

# Хранилище настроек (в идеале использовать БД)
data_store = {
    "greeting": (
        "<b>Привет! Я бот для скачивания медиа.</b> 📥\n\n"
        "Отправь мне ссылку на видео из:\n"
        "• <b>TikTok</b>\n"
        "• <b>Pinterest</b>\n"
        "• <b>Likee</b>\n\n"
        "<i>Просто вставь ссылку в чат, и я пришлю тебе файл!</i>"
    ),
    "users": set()
}

class AdminStates(StatesGroup):
    waiting_for_ad_text = State()
    waiting_for_new_greeting = State()

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- ФУНКЦИЯ СКАЧИВАНИЯ ---
def download_video(url):
    """Используем yt-dlp для получения прямой ссылки на видео"""
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('url')
    except Exception as e:
        logging.error(f"Download error: {e}")
        return None

# --- ВЕБ-СЕРВЕР И САМОПИНГ ---
async def handle(request):
    return web.Response(text="Urban Clash is active!")

async def self_ping():
    await asyncio.sleep(10)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(RENDER_EXTERNAL_URL) as response:
                    logging.info(f"Self-ping: {response.status}")
        except: pass
        await asyncio.sleep(300)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- ОБРАБОТКА ССЫЛОК (TikTok, Pinterest, Likee) ---
@dp.message(F.text.contains("tiktok.com") | F.text.contains("pinterest.com") | F.text.contains("pin.it") | F.text.contains("likee.video"))
async def handle_video_link(message: types.Message):
    wait_msg = await message.answer("⏳ <b>Обрабатываю ссылку...</b>")
    
    video_url = download_video(message.text)
    
    if video_url:
        try:
            video_file = URLInputFile(video_url)
            await message.answer_video(video_file, caption="✅ <b>Готово!</b> @UrbanClashBot")
            await wait_msg.delete()
        except Exception as e:
            await wait_msg.edit_text("❌ Ошибка при отправке видео.")
    else:
        await wait_msg.edit_text("❌ Не удалось получить видео. Проверьте ссылку.")

# --- АДМИНКА ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    data_store["users"].add(message.from_user.id)
    await message.answer(data_store["greeting"])

@dp.message(Command("adminARTEMK101"))
async def admin_panel(message: types.Message):
    buttons = [[InlineKeyboardButton(text="📢 Реклама", callback_data="admin_broadcast")],
               [InlineKeyboardButton(text="👋 Смена приветствия", callback_data="admin_change_greet")]]
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите текст рекламы:")
    await state.set_state(AdminStates.waiting_for_ad_text)
    await callback.answer()

@dp.callback_query(F.data == "admin_change_greet")
async def start_change_greet(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новое приветствие (можно с HTML тегами):")
    await state.set_state(AdminStates.waiting_for_new_greeting)
    await callback.answer()

@dp.message(AdminStates.waiting_for_ad_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    for u_id in data_store["users"]:
        try: await bot.send_message(u_id, message.text)
        except: pass
    await message.answer("✅ Рассылка завершена.")
    await state.clear()

@dp.message(AdminStates.waiting_for_new_greeting)
async def process_new_greeting(message: types.Message, state: FSMContext):
    data_store["greeting"] = message.text
    await message.answer("✅ Приветствие обновлено!")
    await state.clear()

# --- ЗАПУСК ---
async def main():
    asyncio.create_task(start_web_server())
    asyncio.create_task(self_ping())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except:
        pass
