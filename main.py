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
RENDER_EXTERNAL_URL = "https://temki-jgp0.onrender.com" 
ADMIN_ID = 7040863301

# Хранилище (для каналов подписки)
data_store = {
    "greeting": "<b>Привет! Я Urban Clash Bot.</b> 📥\nПришли ссылку из TikTok или Pinterest!",
    "users": set(),
    "channels": [] # Сюда будем добавлять каналы через админку
}

class AdminStates(StatesGroup):
    waiting_for_ad_text = State()
    waiting_for_channel_id = State()
    waiting_for_channel_url = State()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_subscription(user_id):
    for chan in data_store["channels"]:
        try:
            member = await bot.get_chat_member(chat_id=chan["id"], user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except: continue
    return True

def get_sub_kb():
    buttons = [[InlineKeyboardButton(text=f"Канал {i+1}", url=c["url"])] for i, c in enumerate(data_store["channels"])]
    buttons.append([InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ВЕБ-СЕРВЕР И ПИНГ ---
async def handle(request): return web.Response(text="Alive")

async def start_web():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080))).start()

async def self_ping():
    await asyncio.sleep(20)
    while True:
        try:
            async with aiohttp.ClientSession() as s: await s.get(RENDER_EXTERNAL_URL)
        except: pass
        await asyncio.sleep(300)

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    data_store["users"].add(message.from_user.id)
    await message.answer(data_store["greeting"])

@dp.message(F.text.regexp(r'(tiktok\.com|pinterest\.com|pin\.it|likee\.video)'))
async def handle_link(message: types.Message):
    if not await check_subscription(message.from_user.id):
        return await message.answer("⚠️ Подпишитесь на каналы, чтобы скачивать!", reply_markup=get_sub_kb())
    
    m = await message.answer("⏳ Скачиваю...")
    with yt_dlp.YoutubeDL({'format': 'best', 'quiet': True}) as ydl:
        try:
            info = ydl.extract_info(message.text, download=False)
            await message.answer_video(URLInputFile(info['url']), caption="✅ Готово! @UrbanClashBot")
            await m.delete()
        except: await m.edit_text("❌ Ошибка скачивания.")

@dp.callback_query(F.data == "check_subs")
async def check_cb(cb: types.CallbackQuery):
    if await check_subscription(cb.from_user.id):
        await cb.message.edit_text("✅ Теперь присылайте ссылку!")
    else: await cb.answer("❌ Вы не подписались!", show_alert=True)

# --- АДМИНКА ---
@dp.message(Command("adminARTEMK101"))
async def admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_chan")],
        [InlineKeyboardButton(text="🗑 Очистить каналы", callback_data="clear_chans")]
    ])
    await message.answer(f"🛠 Админка. Каналов: {len(data_store['channels'])}", reply_markup=kb)

@dp.callback_query(F.data == "add_chan")
async def add_ch(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("Введите ID канала (например, -100...):")
    await state.set_state(AdminStates.waiting_for_channel_id)

@dp.message(AdminStates.waiting_for_channel_id)
async def ch_id(message: types.Message, state: FSMContext):
    await state.update_data(id=message.text)
    await message.answer("Введите ссылку на канал (https://t.me/...):")
    await state.set_state(AdminStates.waiting_for_channel_url)

@dp.message(AdminStates.waiting_for_channel_url)
async def ch_url(message: types.Message, state: FSMContext):
    d = await state.get_data()
    data_store["channels"].append({"id": d['id'], "url": message.text})
    await message.answer("✅ Канал добавлен!")
    await state.clear()

@dp.callback_query(F.data == "clear_chans")
async def clr(cb: types.CallbackQuery):
    data_store["channels"] = []
    await cb.message.edit_text("🗑 Каналы удалены.")

async def main():
    asyncio.create_task(start_web())
    asyncio.create_task(self_ping())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
