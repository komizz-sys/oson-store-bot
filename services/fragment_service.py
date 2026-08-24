"""
Покупка Stars через официальный API MarketApp (обёртка над Fragment).
Premium через API НЕ покупаем (по решению владельца бота) — Premium-заказы
всегда уходят админу на полностью ручное выполнение.

Как это работает для Stars:
1. Заказ оплачен -> бот вызывает buy_stars()
2. API возвращает готовую TON-транзакцию
3. Бот присылает админу ссылку — тап открывает кошелёк с заполненной транзакцией
4. Админ подтверждает в своём кошельке (Tonkeeper и т.п.)
5. Админ вручную жмёт "Заказ выполнен" в боте после проверки, что всё доставлено
"""

from aiogram import Bot

import config
from services import marketapp_api
from services.ton_deeplink import build_ton_deeplinks


async def try_auto_fulfill_stars(bot: Bot, order: dict) -> None:
    username = order["recipient"].lstrip("@")
    quantity = order["quantity"]

    try:
        tx = await marketapp_api.buy_stars(username, quantity, currency="GRAM")
    except Exception as e:
        await _notify_fail(bot, order, f"Ошибка при покупке звёзд через API: {e}")
        return

    links = build_ton_deeplinks(tx)
    text = (
        f"💳 Заказ #{order['id']} готов к оплате через кошелёк.\n"
        f"Товар: {order['item_name']}\n"
        f"Получатель: {order['recipient']}\n\n"
        f"Открой ссылку в Tonkeeper (или другом TON-кошельке) и подтверди перевод:\n"
        + "\n".join(links)
        + "\n\nПосле подтверждения в кошельке и проверки доставки — "
        "нажми «Заказ выполнен» под чеком этого заказа."
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, disable_web_page_preview=True)
        except Exception:
            pass


async def notify_manual_premium(bot: Bot, order: dict) -> None:
    text = (
        f"👉 Заказ #{order['id']} (Premium) оплачен и ждёт ручного выполнения на fragment.com.\n"
        f"Товар: {order['item_name']}\n"
        f"Получатель: {order['recipient']}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


async def _notify_fail(bot: Bot, order: dict, note: str) -> None:
    text = (
        f"⚠️ Заказ #{order['id']} оплачен, но автопокупка не сработала.\n"
        f"Товар: {order['item_name']}\n"
        f"Получатель: {order['recipient']}\n\n"
        f"{note}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass
