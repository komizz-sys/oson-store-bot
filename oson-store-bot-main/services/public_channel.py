"""
Публикация выполненных заказов в публичный канал — социальное доказательство
для новых клиентов (видно, что бот реально доставляет заказы).

Чтобы включить:
1. Создай Telegram-канал (публичный или приватный)
2. Добавь бота туда админом с правом "Публикация сообщений"
3. Впиши в .env: PUBLIC_ORDERS_CHANNEL=@username_канала (для публичного)
   или числовой ID канала (для приватного, вида -1001234567890 —
   узнать можно переслав любое сообщение из канала боту @userinfobot)

Если PUBLIC_ORDERS_CHANNEL не задан — публикация просто тихо пропускается,
остальной бот работает как обычно.
"""

from aiogram import Bot

import config
from services.prices import format_uzs

CATEGORY_HEADERS = {
    "stars": "⭐ STARS SOTIB OLINDI",
    "premium": "💎 PREMIUM SOTIB OLINDI",
    "simple_gift": "🎁 GIFT SOTIB OLINDI",
    "nft_rent": "🖼 GIFT IJARAGA OLINDI",
}


async def post_completed_order(bot: Bot, order: dict) -> None:
    if not config.PUBLIC_ORDERS_CHANNEL:
        return

    header = CATEGORY_HEADERS.get(order["category"], "📦 BUYURTMA BAJARILDI")

    lines = [
        f"📦 <b>{header} - #{order['id']}</b>",
        "",
        f"🎯 <b>Qabul qiluvchi:</b> {order['recipient']}",
    ]

    if order["category"] == "nft_rent" and order.get("rent_days"):
        lines.append(f"🗓 <b>Muddat:</b> {order['rent_days']} kun")
    else:
        lines.append(f"⭐ <b>Mahsulot:</b> {order['item_name']}")

    lines.append(f"💰 <b>Narxi:</b> {format_uzs(order['price_uzs'])}")
    lines.append("")
    lines.append("🔔 <b>Holat:</b> Bajarildi✅")

    try:
        await bot.send_message(config.PUBLIC_ORDERS_CHANNEL, "\n".join(lines))
    except Exception:
        pass  # канал недоступен/бот не админ — не роняем основной флоу заказа
