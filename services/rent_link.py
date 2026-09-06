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
    "🎥 Как получить твой арендованный подарок:\n\n"
    "Посмотри видео выше — там показано, как получить свою персональную "
    "ссылку для подключения подарка в Telegram.\n\n"
    "После этого пришли мне сюда, в этот же чат, саму ссылку. Как только я "
    "подключу тебе гифт — сразу напишу."
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
