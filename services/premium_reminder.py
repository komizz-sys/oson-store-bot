"""
Напоминание клиентам, купившим Telegram Premium, через РОВНО 30 дней —
подписка Premium обычно на месяц, так что это естественный момент
предложить продлить. Текст — на языке, который клиент выбрал при /start.

Работает фоновой задачей рядом с polling бота (см. bot.py) — раз в 6 часов
проверяет, не появились ли заказы Premium ровно 30-дневной давности, которым
ещё не отправляли напоминание.

ТРЕБУЕТСЯ добавить в БД (см. database/db.py):
1) Миграция:  ALTER TABLE orders ADD COLUMN reminder_sent INTEGER DEFAULT 0
2) Функции:   get_premium_orders_due_for_reminder() и mark_reminder_sent(order_id)
   — их код смотри в reminder_db_snippet.py рядом с этим файлом, просто
   вставь в свой database/db.py (я его не трогаю, чтобы не откатить твои правки).
"""

import asyncio

from aiogram import Bot

REMINDER_TEXT = {
    "uz": "👋 Salom! Telegram Premium obunangiz ertaga tugaydi ⏳\n\nUzmay davom ettirish uchun shu botdan yana sotib olishingiz mumkin — narxlar avvalgidek qulay 💎",
    "ru": "👋 Привет! Ваша подписка Telegram Premium заканчивается завтра ⏳\n\nЧтобы не прерывать её, можно купить снова прямо в этом боте — цены прежние 💎",
    "en": "👋 Hi! Your Telegram Premium subscription ends tomorrow ⏳\n\nYou can renew it right here in the bot — same great prices 💎",
}
SHOP_HINT = {
    "uz": "\n\n🛍 Pastdagi \"Do'konni ochish\" tugmasi orqali xarid qilishingiz mumkin.",
    "ru": "\n\n🛍 Оформить можно через кнопку «Do'konni ochish» внизу чата.",
    "en": "\n\n🛍 You can order via the \"Do'konni ochish\" button at the bottom of the chat.",
}

CHECK_INTERVAL_SECONDS = 6 * 60 * 60  # раз в 6 часов — достаточно, чтобы не пропустить нужный день


async def premium_reminder_loop(bot: Bot):
    # Импорт внутри функции, чтобы этот модуль не падал на импорте, если
    # функции в database/db.py ещё не добавлены — сам цикл просто не запустится.
    from database.db import get_premium_orders_due_for_reminder, mark_reminder_sent, get_user_language

    while True:
        try:
            orders = await get_premium_orders_due_for_reminder()
            for order in orders:
                lang = await get_user_language(order["user_id"])
                lang = lang if lang in ("uz", "ru", "en") else "uz"
                try:
                    await bot.send_message(
                        order["user_id"],
                        REMINDER_TEXT[lang] + SHOP_HINT[lang],
                    )
                except Exception:
                    pass  # человек мог заблокировать бота и т.п. — не критично, просто пропускаем
                await mark_reminder_sent(order["id"])
        except Exception as e:
            print(f"[premium_reminder_loop] ошибка: {e}", flush=True)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
