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
        "🎥 <b>Videoda hammasi ko'rsatilgan:</b>\n\n"
        "1️⃣ <b>fragment.com</b> dan shaxsiy havolani qanday olish\n"
        "2️⃣ Sovg'ani profilda qanday ko'rsatish\n\n"
        "Havolani olgach — <b>do'konni oching</b> va uni \"Aktiv buyurtma\" "
        "bo'limidagi maydonga joylang ✅"
    ),
    "ru": (
        "🎥 <b>В видео показано всё:</b>\n\n"
        "1️⃣ как получить персональную ссылку на <b>fragment.com</b>\n"
        "2️⃣ как показать подарок в профиле\n\n"
        "Получили ссылку — <b>откройте магазин</b> и вставьте её в поле "
        "в блоке «Активный заказ» ✅"
    ),
    "en": (
        "🎥 <b>The video shows everything:</b>\n\n"
        "1️⃣ how to get your personal link on <b>fragment.com</b>\n"
        "2️⃣ how to display the gift on your profile\n\n"
        "Once you have the link — <b>open the shop</b> and paste it into the "
        "field in the \"Active order\" block ✅"
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
