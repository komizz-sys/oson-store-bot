import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.db import init_db, expire_stale_unpaid_orders
from services.stats_api import start_stats_server
from handlers import user, admin, order, payment, webapp, support, rent_link, sms_payment

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
            for order in expired:
                try:
                    await bot.send_message(
                        order["user_id"],
                        f"⌛ Заказ #{order['id']} отменён — истекло время на оплату. "
                        "Если ещё актуально, оформите заново через /start.",
                    )
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
    dp.include_router(order.router)
    dp.include_router(payment.router)
    dp.include_router(user.router)
    # Последним — ловит только "голую" ссылку от клиента, привязанную к его
    # оплаченному заказу аренды; если такого заказа нет, пропускает сообщение
    # дальше, так что должен идти после всех остальных роутеров.
    dp.include_router(rent_link.router)

    await bot.delete_webhook(drop_pending_updates=True)

    # Сбрасываем старый Menu Button, если он был установлен раньше — иначе
    # он остаётся висеть в Telegram даже после удаления кода, который его
    # ставил, и создаёт путаницу с новой кнопкой-клавиатурой магазина.
    from aiogram.types import MenuButtonDefault
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
    except Exception:
        pass

    # Внутренний API для бота-аналитика (доход/расход/прибыль) — если не
    # настроен через ANALYTICS_API_SECRET, просто ничего не делает
    await start_stats_server()

    if config.UNIQUE_AMOUNT_ENABLED:
        asyncio.create_task(_expire_stale_orders_loop(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
