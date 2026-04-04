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
ADMIN_ID = 7040863301  # Твой личный ID для доступа к админке

# Хранилище настроек (сбрасывается при перезагрузке сервера)
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

# --- ВЕБ-СЕРВЕР И САМОПИНГ (ДЛЯ RENDER) ---
async def handle(request):
    return web.Response(text="Urban Clash is active!")

async def self_ping():
    await asyncio.sleep(10)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(RENDER_EXTERNAL_URL) as response:
                    logging.info(f"Self-ping status: {response.status}")
        except: pass
        await asyncio.sleep(300) # 5 минут

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- ОБРАБОТКА ССЫЛОК ---
@dp.message(F.text.regexp(r'(tiktok\.com|pinterest\.com|pin\.it|likee\.video)'))
async def handle_video_link(message: types.Message):
    wait_msg = await message.answer("⏳ <b>Обрабатываю ссылку...</b>")
    
    video_url = download_video(message.text)
    
    if video_url:
        try:
            video_file = URLInputFile(video_url)
            await message.answer_video(video_file, caption="✅ <b>Готово!</b>")
            await wait_msg.delete()
        except Exception as e:
            await wait_msg.edit_text("❌ Ошибка при отправке видео.")
    else:
        await wait_msg.edit_text("❌ Не удалось получить видео. Возможно, ссылка неверна.")

# --- АДМИНКА ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    data_store["users"].add(message.from_user.id)
    await message.answer(data_store["greeting"])

@dp.message(Command("adminARTEMK101"))
async def admin_panel(message: types.Message):
    # ПРОВЕРКА АЙДИ
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ Доступ запрещен. Вы не являетесь администратором.")
        return

    buttons = [
        [InlineKeyboardButton(text="📢 Реклама", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👋 Изменить приветствие", callback_data="admin_change_greet")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("🛠 <b>Админ-панель проекта</b>\n\nДоступ разрешен для ID: <code>7040863301</code>", reply_markup=kb)

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите текст рекламы для рассылки:")
    await state.set_state(AdminStates.waiting_for_ad_text)
    await callback.answer()

@dp.callback_query(F.data == "admin_change_greet")
async def start_change_greet(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новое приветствие (можно HTML):")
    await state.set_state(AdminStates.waiting_for_new_greeting)
    await callback.answer()

@dp.message(AdminStates.waiting_for_ad_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    sent_count = 0
    for u_id in data_store["users"]:
        try:
            await bot.send_message(u_id, message.text)
            sent_count += 1
        except: pass
    await message.answer(f"✅ Рассылка завершена! Получателей: {sent_count}")
    await state.clear()

@dp.message(AdminStates.waiting_for_new_greeting)
async def process_new_greeting(message: types.Message, state: FSMContext):
    data_store["greeting"] = message.text
    await message.answer("✅ Новое приветствие сохранено!")
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
