import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.db import init_db
from handlers import user, admin, order, payment, webapp, support

logging.basicConfig(level=logging.INFO)


async def main():
    await init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: сначала специфичные роутеры, потом общие
    dp.include_router(admin.router)
    dp.include_router(support.router)
    dp.include_router(webapp.router)
    dp.include_router(order.router)
    dp.include_router(payment.router)
    dp.include_router(user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
