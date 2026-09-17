import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.db import init_db, expire_stale_unpaid_orders
from services.stats_api import start_stats_server
from handlers import user, admin, order, payment, webapp, support, rent_link, sms_payment, cart

logging.basicConfig(level=logging.INFO)


async def _expire_stale_orders_loop(bot: Bot):
    """
    Каждые 5 минут отменяет неоплаченные заказы старше UNIQUE_AMOUNT_ORDER_TTL_MINUTES
    и освобождает их уникальную сумму — иначе занятые суммы копились бы вечно и
    рано или поздно кончился бы диапазон (UNIQUE_AMOUNT_MAX_OFFSET).
    """
    while True:
        try:
            expired = await expire_stale_unpaid_orders()
            # Товары одной корзины просрочиваются все разом — шлём ОДНО
            # сообщение на корзину, а не по сообщению на каждый товар.
            notified_carts = set()
            for order in expired:
                cart_id = order.get("cart_id")
                if cart_id:
                    if cart_id in notified_carts:
                        continue
                    notified_carts.add(cart_id)
                    text = (
                        "⌛ Корзина отменена — истекло время на оплату. "
                        "Если ещё актуально, соберите заново в магазине."
                    )
                else:
                    text = (
                        f"⌛ Заказ #{order['id']} отменён — истекло время на оплату. "
                        "Если ещё актуально, оформите заново через /start."
                    )
                try:
                    await bot.send_message(order["user_id"], text)
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"Ошибка в фоновой проверке просроченных заказов: {e}")
        await asyncio.sleep(5 * 60)


async def main():
    await init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: сначала специфичные роутеры, потом общие
    dp.include_router(sms_payment.router)
    dp.include_router(admin.router)
    dp.include_router(support.router)
    dp.include_router(webapp.router)
    # Корзина — раньше order/payment: у неё свои callback'и (cart:confirm),
    # и они не должны спорить с подтверждением одиночного заказа.
    dp.include_router(cart.router)
    dp.include_router(order.router)
    dp.include_router(payment.router)
    dp.include_router(user.router)
    # Последним — ловит только "голую" ссылку от клиента, привязанную к его
    # оплаченному заказу аренды; если такого заказа нет, пропускает сообщение
    # дальше, так что должен идти после всех остальных роутеров.
    dp.include_router(rent_link.router)

    await bot.delete_webhook(drop_pending_updates=True)

    # Раньше сбрасывали Menu Button на дефолт, потому что через неё не
    # работал sendData() — заказ мог "потеряться". Теперь заказ идёт через
    # защищённый API (/public/create_order, та же подпись initData, что и у
    # Tarix/TOP/Profil), а не через sendData(), так что Menu Button можно
    # спокойно включать — компактная кнопка "Открыть" у поля ввода.
    # Список команд в меню "/" — чтобы /operator и /start были на виду
    from aiogram.types import BotCommand
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🛍 Do'kon / Магазин"),
            BotCommand(command="operator", description="💬 Operator / Оператор"),
        ])
    except Exception:
        pass

    from aiogram.types import MenuButtonWebApp, WebAppInfo
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Открыть", web_app=WebAppInfo(url=config.WEBAPP_URL))
        )
    except Exception:
        pass

    # Внутренний API для бота-аналитика (доход/расход/прибыль) — если не
    # настроен через ANALYTICS_API_SECRET, просто ничего не делает
    await start_stats_server(bot, dp.storage)

    # Напоминания о продлении Premium (раз в 6 часов проверяет подписки,
    # которым скоро месяц, и шлёт "заканчивается завтра")
    from services.premium_reminder import premium_reminder_loop
    asyncio.create_task(premium_reminder_loop(bot))

    if config.UNIQUE_AMOUNT_ENABLED:
        asyncio.create_task(_expire_stale_orders_loop(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
