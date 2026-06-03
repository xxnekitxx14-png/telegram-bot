import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = "7775197329:AAE0yd3a5qJu-E46HX72TN4Y4zNLcslXweU"
ADMIN_ID  = 295249209

GROUPS = {
    "акулы": {"name": "Акулы продаж", "id": -1003305660572},
    "стат":  {"name": "Статистика",   "id": -1003905669709},
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
scheduler = AsyncIOScheduler()
message_buffer = {}

class SendMessage(StatesGroup):
    waiting_for_group = State()

def is_active_time():
    return 20 <= datetime.now().hour <= 23

def group_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    for key, g in GROUPS.items():
        keyboard.add(types.InlineKeyboardButton(text=g["name"], callback_data=f"group_{key}"))
    return keyboard

@dp.message_handler(commands=["start", "help"], chat_type="private")
async def cmd_help(message: types.Message):
    await message.answer("👋 Привет!\n\n📨 Напиши сообщение — выберу группу кнопкой\n\n⏰ /schedule 21:00 акулы Текст\n⏰ /schedule 21:00 стат Текст\n\n📋 Каждый час с 20:00 до 00:00 шлю сводку")

@dp.message_handler(chat_type="private", state="*")
async def ask_group(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or message.text.startswith("/"):
        return
    await state.update_data(text=message.text)
    await SendMessage.waiting_for_group.set()
    await message.answer("📤 В какую группу отправить?", reply_markup=group_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith("group_"), state=SendMessage.waiting_for_group)
async def send_to_group(callback: types.CallbackQuery, state: FSMContext):
    key = callback.data.replace("group_", "")
    group = GROUPS.get(key)
    if not group:
        return
    data = await state.get_data()
    await bot.send_message(chat_id=group["id"], text=data.get("text", ""))
    await callback.message.edit_text(f"✅ Отправлено в «{group['name']}»!")
    await state.finish()

@dp.message_handler(commands=["schedule"], chat_type="private")
async def cmd_schedule(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(" ", 3)
    if len(parts) < 4:
        await message.answer("❌ Формат: /schedule 21:00 акулы Текст")
        return
    time_str, group_key, text = parts[1], parts[2].lower(), parts[3]
    group = GROUPS.get(group_key)
    if not group:
        await message.answer("❌ Используй: акулы или стат")
        return
    try:
        hour, minute = map(int, time_str.split(":"))
    except ValueError:
        await message.answer("❌ Формат времени: 21:00")
        return
    now = datetime.now()
    send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if send_time <= now:
        send_time += timedelta(days=1)
    scheduler.add_job(send_scheduled, "date", run_date=send_time, args=[group["id"], text])
    await message.answer(f"⏰ Запланировано на {time_str} в «{group['name']}»:\n{text}")

async def send_scheduled(chat_id, text):
    await bot.send_message(chat_id=chat_id, text=text)

@dp.message_handler(chat_type=["group", "supergroup"])
async def collect_message(message: types.Message):
    if not is_active_time():
        return
    chat_id = message.chat.id
    if chat_id not in message_buffer:
        message_buffer[chat_id] = {"title": message.chat.title or "Группа", "lines": []}
    message_buffer[chat_id]["lines"].append(message.text or "📎 Медиафайл")

async def send_hourly_digest():
    while True:
        now = datetime.now()
        await asyncio.sleep((60 - now.minute) * 60 - now.second)
        now = datetime.now()
        if not is_active_time():
            message_buffer.clear()
            continue
        if not message_buffer:
            await bot.send_message(chat_id=ADMIN_ID, text=f"🕐 {now.strftime('%H:00')} — сообщений не было.")
            continue
        for chat_id, data in message_buffer.items():
            if not data["lines"]:
                continue
            full_text = f"📋 Сводка за {now.strftime('%H:00')} | {data['title']} | {len(data['lines'])} сообщ.\n\n" + "\n".join(data["lines"])
            for i in range(0, len(full_text), 4000):
                await bot.send_message(chat_id=ADMIN_ID, text=full_text[i:i+4000])
        message_buffer.clear()

async def on_startup(dp):
    scheduler.start()
    asyncio.create_task(send_hourly_digest())

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
