"""
После оплаты аренды NFT-подарка клиенту нужно самому получить в Telegram
персональную ссылку для подключения гифта (через Fragment "Assign to
Telegram") и вставить её в мини-аппе — бот подключит подарок автоматически.

Видео-инструкция настраивается один раз через config.RENT_TUTORIAL_VIDEO
(Telegram file_id — получить его через /getfileid) и не зависит от диска
на Railway (file_id живёт вечно, пока не поменяли токен бота).
"""

from aiogram import Bot

import config
from database.db import get_user_language

# Текст на 3 языках — показываем на том, что клиент выбрал при /start.
RENT_LINK_PROMPT = {
    "uz": (
        "🎥 <b>Ijaraga olgan sovg'angizni qanday olish mumkin:</b>\n\n"
        "Yuqoridagi videoni ko'ring — unda Telegram'da sovg'ani ulash uchun "
        "shaxsiy havolangizni qanday olish ko'rsatilgan.\n\n"
        "So'ngra <b>do'konni oching</b> va havolani yuqoridagi \"Aktiv buyurtma\" "
        "bo'limidagi maydonga joylang — sovg'a avtomatik ulanadi ✅"
    ),
    "ru": (
        "🎥 <b>Как получить арендованный подарок:</b>\n\n"
        "Посмотрите видео выше — там показано, как получить свою персональную "
        "ссылку для подключения подарка в Telegram.\n\n"
        "Затем <b>откройте магазин</b> и вставьте ссылку в поле в блоке "
        "«Активный заказ» — подарок подключится автоматически ✅"
    ),
    "en": (
        "🎥 <b>How to get your rented gift:</b>\n\n"
        "Watch the video above — it shows how to get your personal link to "
        "connect the gift in Telegram.\n\n"
        "Then <b>open the shop</b> and paste the link into the field in the "
        "\"Active order\" block — the gift will be connected automatically ✅"
    ),
}


async def send_rent_link_tutorial(bot: Bot, order: dict) -> None:
    lang = await get_user_language(order["user_id"])
    text = RENT_LINK_PROMPT.get(lang if lang in RENT_LINK_PROMPT else "uz")

    if config.RENT_TUTORIAL_VIDEO:
        try:
            await bot.send_video(
                order["user_id"],
                config.RENT_TUTORIAL_VIDEO,
                caption=text,
            )
            return
        except Exception:
            pass  # file_id мог устареть — не молчим, шлём хотя бы текст

    await bot.send_message(order["user_id"], text)
