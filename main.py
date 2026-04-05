import os
import asyncio
import logging
import sqlite3
import time
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
import yt_dlp

# --- СОСТОЯНИЯ ДЛЯ ДОНАТОВ И АДМИНКИ ---
class BotStates(StatesGroup):
    wait_donation_amount = State() # Ждем число звезд
    wait_broadcast = State()      # Ждем текст рассылки
    wait_new_start_text = State() # Ждем новое приветствие

# --- КОНФИГУРАЦИЯ ---
raw_token = os.getenv("BOT_TOKEN", "").strip().replace(" ", "")
TOKEN = raw_token
ADMIN_ID = 7040863301  # Твой ID
PORT = int(os.getenv("PORT", 8080))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()

# Токен провайдера (получить у @BotFather -> Payments)
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "").strip() 

BOT_NAME = "Save Lyneok Videos 🏁"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ (Расширенная) ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect("bot_master.db")
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
    # Начальное приветствие
    db_query("INSERT OR IGNORE INTO settings VALUES ('start_text', 'Привет! Я Save Lyneok Videos 🏁\nОтправь мне ссылку из TikTok, Likee или Pinterest!')")

init_db()

# --- ТЕХНИКА СКАЧИВАНИЯ (Исправленная и Усиленная) ---
def download_content(url):
    filename_base = f"video_{int(time.time())}"
    output_template = f"{filename_base}.%(ext)s"
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        # Жесткая имитация реального браузера
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
        'add_header': [
            'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language:ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'
        ],
        'http_chunk_size': 1048576,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# --- ГЛАВНОЕ АДМИН-МЕНЮ (Новое на кнопках) ---
def get_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📝 Сменить /start", callback_data="adm_set_text")],
        [InlineKeyboardButton(text="🚫 Блок юзера (ID)", callback_data="adm_ban_user")],
        [InlineKeyboardButton(text="🔗 ОП Каналы", callback_data="adm_channels")],
        [InlineKeyboardButton(text="❌ Очистить каналы", callback_data="adm_clear_ch")]
    ])

# --- АДМИН ХЕНДЛЕРЫ (Интерактивные) ---

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_start(message: types.Message):
    await message.answer(f"🛠 **Управление {BOT_NAME}**", reply_markup=get_admin_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "adm_broadcast", F.from_user.id == ADMIN_ID)
async def broadcast_step1(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.wait_broadcast)
    await call.message.answer("Введите текст для рассылки всем пользователям:")
    await call.answer()

@dp.message(BotStates.wait_broadcast)
async def broadcast_step2(message: types.Message, state: FSMContext):
    users = db_query("SELECT id FROM users", fetch=True)
    count = 0
    await message.answer("🚀 *Начинаю рассылку...*", parse_mode="Markdown")
    for u in users:
        try:
            await bot.send_message(u[0], message.text)
            count += 1
        except: pass
    await message.answer(f"✅ Готово! Рассылка отправлена {count} пользователям.")
    await state.clear()

@dp.callback_query(F.data == "adm_set_text", F.from_user.id == ADMIN_ID)
async def set_text_step1(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.wait_new_start_text)
    await call.message.answer("Введите новый текст приветствия (/start):")
    await call.answer()

@dp.message(BotStates.wait_new_start_text)
async def set_text_step2(message: types.Message, state: FSMContext):
    db_query("UPDATE settings SET value = ? WHERE key = 'start_text'", (message.text,))
    await message.answer("✅ Текст приветствия обновлен!")
    await state.clear()

# --- ЛОГИКА СКАЧИВАНИЯ ДЛЯ ЮЗЕРОВ (С КНОПКАМИ ДОНАТА) ---

# Кнопки ДА/НЕТ для доната
def get_donate_prompt_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, поддержать бота", callback_data="donate_yes")],
        [InlineKeyboardButton(text="❌ НЕТ", callback_data="donate_no")]
    ])

@dp.message(F.text.regexp(r'(https?://[^\s]+)'))
async def handle_dl_request(message: types.Message):
    # Проверка на бан
    user = db_query("SELECT status FROM users WHERE id = ?", (message.from_user.id,), fetch=True)
    if user and user[0][0] == 'banned':
        return await message.answer("❌ *Вы заблокированы админом.*", parse_mode="Markdown")
    
    db_query("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    
    url = message.text.strip()
    status_msg = await message.answer("⏳ *Начинаю загрузку видео...*", parse_mode="Markdown")
    logger.info(f"Download request from {message.from_user.id} for URL: {url}")
    
    try:
        # Скачивание в фоновом потоке
        path = await asyncio.to_thread(download_content, url)
        
        if os.path.exists(path):
            # Отправка видео
            video_file = FSInputFile(path)
            await message.reply_video(video=video_file, caption=f"Готово! {BOT_NAME} 🏁")
            await status_msg.delete()
            
            # Сразу удаляем файл
            os.remove(path)
            logger.info(f"File {path} sent and deleted.")
            
            # --- НОВОЕ СООБЩЕНИЕ ПРО ДОНАТ ---
            donate_text = (
                "🎁 Спасибо за использование бота!\n\n"
                "Если хотите поддержать проект, можете пожертвовать несколько звезд ⭐?\n"
                "Это поможет боту работать быстрее и стабильнее!"
            )
            await message.answer(donate_text, reply_markup=get_donate_prompt_kb())
            
        else:
            raise FileNotFoundError("File not downloaded")

    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text("❌ *Ошибка!* \nНе удалось скачать видео. Проверьте ссылку.")

# --- ЛОГИКА ОПЛАТЫ (TELEGRAM STARS) ---

@dp.callback_query(F.data == "donate_no")
async def donate_cancelled(call: types.CallbackQuery, state: FSMContext):
    await state.clear() # Сбрасываем состояния, если юзер передумал
    txt = db_query("SELECT value FROM settings WHERE key = 'start_text'", fetch=True)[0][0]
    await call.message.edit_text(txt + "\n\n(Жду новую ссылку 🏁)")
    await call.answer()

@dp.callback_query(F.data == "donate_yes")
async def donate_confirmed(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.wait_donation_amount)
    await call.message.edit_text("💖 Отлично! Напишите, сколько вы можете пожертвовать звезд? ⭐\n*(Напишите число ОТ 5)*")
    await call.answer()

@dp.message(BotStates.wait_donation_amount, F.text.regexp(r'^\d+$'))
async def generate_invoice_step(message: types.Message, state: FSMContext):
    amount_stars = int(message.text)
    
    if amount_stars < 5:
        return await message.answer("⚠️ Минимальная сумма пожертвования — 5 звезд ⭐. Попробуйте еще раз.")
    
    await state.clear()
    
    status = await message.answer("⏳ Генерирую чек для оплаты...")
    
    try:
        # Генерация инвойса на оплату (Stars)
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Пожертвование боту ⭐",
            description=f"Thanks for supporting {BOT_NAME}! Contribution🏁",
            payload=f"donate_{message.from_user.id}_{amount_stars}", # Уникальный ID платежа
            provider_token=PROVIDER_TOKEN,
            start_parameter="donate_start",
            currency="XTR", # Код для Telegram Stars
            prices=[LabeledPrice(label="Пожертвование 🏁", amount=amount_stars)],
            # Настройки, чтобы чек был красивым, как на фото (Товар: Пожертвование)
        )
        await status.delete()
        
    except Exception as e:
        logger.error(f"Invoice error: {e}")
        await status.edit_text("❌ Ошибка при создании чека. Попробуйте позже или свяжитесь с админом.")

# Хендлер для тех, кто ввел не число в состоянии FSM
@dp.message(BotStates.wait_donation_amount)
async def donation_amount_error(message: types.Message):
    await message.answer("⚠️ Пожалуйста, напишите **только целое число** (например, 10 или 50). Минимум 5.")

# --- ОБРАБОТКА УСПЕШНОЙ ОПЛАТЫ ---

# 1. Сначала ПреЧек (PreCheckout) - обязательно для Telegram
@dp.pre_checkout_query(lambda q: True)
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# 2. Обработка успешного платежа
@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    # Парсим payload (donate_{user_id}_{stars})
    _, user_id, stars = payload.split('_')
    
    logger.info(f"PAYMENT SUCCESS! User {user_id} donated {stars} stars.")
    
    # Сообщение благодарности пользователю
    await message.answer(f"💖 Оплата прошла успешно!\n**Огромное спасибо за пожертвование в {stars} звезд ⭐!**\n\nВы делаете бота лучше! Save Lyneok Videos 🏁")
    
    # Уведомление админу (тебе)
    try:
        await bot.send_message(ADMIN_ID, f"🎉🎉🎉 **УРА! Вам пожертвовали!**\n\nПользователь `{user_id}` пожертвовал **{stars} звезд ⭐!**")
    except: pass

# --- ОБЫЧНЫЙ СТАРТ ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    db_query("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    txt = db_query("SELECT value FROM settings WHERE key = 'start_text'", fetch=True)[0][0]
    
    channels = db_query("SELECT url FROM channels", fetch=True)
    kb = None
    if channels:
        btns = [[InlineKeyboardButton(text="📢 Подписаться (ОП)", url=c[0])] for c in channels]
        kb = InlineKeyboardMarkup(inline_keyboard=btns)
    
    await message.answer(txt, reply_markup=kb, parse_mode="Markdown")

# --- ПРОБУЖДЕНИЕ ДЛЯ RENDER ---
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
    # Веб-сервер для порта Render
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
