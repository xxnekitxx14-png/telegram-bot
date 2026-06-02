"""
Telegram-бот: собирает сообщения из группы с 20:00 до 00:00
и каждый час отправляет одним большим текстом администратору.

Установка:
    pip install aiogram

Настройка:
    1. Создай бота через @BotFather → получи BOT_TOKEN
    2. Узнай свой ADMIN_ID через @userinfobot
    3. Добавь бота в группу как администратора
    4. Заполни BOT_TOKEN и ADMIN_ID ниже
    5. Запусти: python bot.py
"""

import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command

# ───────────────────────────────────────────
#  НАСТРОЙКИ — заполни перед запуском
# ───────────────────────────────────────────
BOT_TOKEN = "7775197329:AAE0yd3a5qJu-E46HX72TN4Y4zNLcslXweU"   # токен от @BotFather
ADMIN_ID  = 295249209          # твой Telegram user_id
# ───────────────────────────────────────────

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# Буфер: { chat_id: { title: str, lines: [str] } }
message_buffer: dict[int, dict] = {}


def is_active_time() -> bool:
    """Возвращает True если сейчас с 20:00 до 00:00."""
    now = datetime.now()
    return 20 <= now.hour <= 23


@dp.message(Command("start"))
async def cmd_start(message: Message):
    if message.chat.type == "private":
        await message.answer(
            "👋 Бот запущен!\n"
            "Добавь меня в группу как администратора.\n"
            "С 20:00 до 00:00 буду собирать сообщения "
            "и каждый час присылать тебе всё одним текстом."
        )


@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def collect_message(message: Message):
    """Собирает сообщения в буфер только в активное время."""
    if not is_active_time():
        return

    chat_id = message.chat.id
    if chat_id not in message_buffer:
        message_buffer[chat_id] = {
            "title": message.chat.title or "Группа",
            "lines": []
        }

    text = message.text or message.caption or "📎 Медиафайл"
    message_buffer[chat_id]["lines"].append(text)


async def send_hourly_digest():
    """Отправляет сводку каждый час и очищает буфер."""
    while True:
        now = datetime.now()

        # Ждём до следующего полного часа
        seconds_to_wait = (60 - now.minute) * 60 - now.second
        await asyncio.sleep(seconds_to_wait)

        now = datetime.now()

        # Работаем только с 20:00 до 00:00
        if not is_active_time():
            message_buffer.clear()
            continue

        if not message_buffer:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🕐 {now.strftime('%H:00')} — сообщений за этот час не было."
            )
            continue

        for chat_id, data in message_buffer.items():
            lines = data["lines"]
            if not lines:
                continue

            title = data["title"]
            header = f"📋 Сводка за {now.strftime('%H:00')} | {title} | {len(lines)} сообщ.\n\n"
            body = "\n".join(lines)
            full_text = header + body

            # Разбиваем если текст длиннее 4096 символов (лимит Telegram)
            for i in range(0, len(full_text), 4000):
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=full_text[i:i+4000]
                )

        message_buffer.clear()


async def main():
    print("✅ Бот запущен. Сбор сообщений с 20:00 до 00:00.")
    await asyncio.gather(
        dp.start_polling(bot),
        send_hourly_digest()
    )


if __name__ == "__main__":
    asyncio.run(main())
