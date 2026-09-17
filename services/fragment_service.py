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

    # Сначала пробуем оплатить сами — клиент уже заплатил, ждать админа с
    # телефоном незачем. Если автоплатёж выключен или не сработал, ниже идёт
    # прежний путь с ручной ссылкой.
    from services.ton_autopay import autopay_or_none
    from keyboards.admin_kb import admin_fulfill_kb

    paid = await autopay_or_none(
        bot, tx, order, purpose="stars", what=f"звёзды {order['item_name']}"
    )
    if paid:
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⭐ Заказ #{order['id']}: {order['item_name']} → {order['recipient']}.\n"
                    "Оплата ушла автоматически. Проверь доставку и нажми «Заказ выполнен».",
                    reply_markup=admin_fulfill_kb(order["id"]),
                )
            except Exception:
                pass
        return

    links = build_ton_deeplinks(tx)
    links_block = "\n".join(f"<code>{link}</code>" for link in links)
    text = (
        f"💳 Заказ #{order['id']} готов к оплате через кошелёк.\n"
        f"Товар: {order['item_name']}\n"
        f"Получатель: {order['recipient']}\n\n"
        f"Открой ссылку в Tonkeeper (или другом TON-кошельке) и подтверди перевод:\n"
        + links_block
        + "\n\nПосле подтверждения в кошельке и проверки доставки — "
        "нажми «Заказ выполнен» под чеком этого заказа."
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, text, disable_web_page_preview=True,
                reply_markup=admin_fulfill_kb(order["id"]),
            )
        except Exception:
            pass


async def notify_manual_premium(bot: Bot, order: dict) -> None:
    from keyboards.admin_kb import admin_fulfill_kb

    text = (
        f"👉 Заказ #{order['id']} (Premium) оплачен и ждёт ручного выполнения на fragment.com.\n"
        f"Товар: {order['item_name']}\n"
        f"Получатель: {order['recipient']}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=admin_fulfill_kb(order["id"]))
        except Exception:
            pass


async def _notify_fail(bot: Bot, order: dict, note: str) -> None:
    """
    Автопокупка не прошла. К сообщению обязательно цепляем кнопку отмены:
    заказ уже в статусе «оплачен» и у клиента висит в витрине активным —
    без кнопки его нельзя ни выполнить, ни закрыть.
    """
    from keyboards.admin_kb import admin_cancel_kb

    text = (
        f"⚠️ Заказ #{order['id']} оплачен, но автопокупка не сработала.\n"
        f"Товар: {order['item_name']}\n"
        f"Получатель: {order['recipient']}\n\n"
        f"{note}\n\n"
        "Выполни вручную или отмени заказ кнопкой ниже — иначе он останется "
        "висеть у клиента как активный."
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=admin_cancel_kb(order["id"]))
        except Exception:
            pass
