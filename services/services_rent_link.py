"""
После оплаты аренды NFT-подарка клиенту нужно самому получить в Telegram
персональную ссылку для подключения гифта (через Fragment "Assign to
Telegram") и прислать её в этот же бот — чтобы админ не путался, к какому
заказу какая ссылка относится, и чтобы личка админа не переполнялась.

Видео-инструкция настраивается один раз через config.RENT_TUTORIAL_VIDEO
(Telegram file_id — получить его через /getfileid) и не зависит от диска
на Railway (файл-id живёт вечно, пока не поменяли токен бота).
"""

from aiogram import Bot

import config

RENT_LINK_PROMPT = (
    "🎥 Ijaraga olgan giftingizni qanday olish mumkin:\n\n"
    "Yuqoridagi videoni ko‘ring — unda Telegram’da giftingizni ulash uchun "
    "shaxsiy havolangizni qanday olish ko‘rsatilgan.\n\n"
    "Shundan so‘ng, havolani aynan shu chatga yuboring. Men giftingizni ulab "
    "berganimdan so‘ng, darhol sizga xabar beraman. Va siz videodagidak "
    "profilingizga chiqarib olasiz!"
)


async def send_rent_link_tutorial(bot: Bot, order: dict) -> None:
    if config.RENT_TUTORIAL_VIDEO:
        try:
            await bot.send_video(
                order["user_id"],
                config.RENT_TUTORIAL_VIDEO,
                caption=RENT_LINK_PROMPT,
            )
            return
        except Exception:
            pass  # file_id мог устареть/быть неверным — не молчим, шлём хотя бы текст

    await bot.send_message(order["user_id"], RENT_LINK_PROMPT)
