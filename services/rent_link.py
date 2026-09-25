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
        "🎥 <b>Video ko'rsatmani tanlang</b> — telefoningizga mosini bosing 👇\n\n"
        "Videoda: <b>fragment.com</b> dan havolani qanday olish va sovg'ani "
        "profilda qanday ko'rsatish.\n\n"
        "Havolani olgach — <b>do'konni oching</b> va uni \"Aktiv buyurtma\" "
        "bo'limidagi maydonga joylang ✅"
    ),
    "ru": (
        "🎥 <b>Выберите видео-инструкцию</b> — для своего телефона 👇\n\n"
        "В видео: как получить ссылку на <b>fragment.com</b> и как показать "
        "подарок в профиле.\n\n"
        "Получили ссылку — <b>откройте магазин</b> и вставьте её в поле "
        "в блоке «Активный заказ» ✅"
    ),
    "en": (
        "🎥 <b>Pick your video guide</b> — the one for your phone 👇\n\n"
        "It shows how to get the link on <b>fragment.com</b> and how to "
        "display the gift on your profile.\n\n"
        "Once you have the link — <b>open the shop</b> and paste it into the "
        "field in the \"Active order\" block ✅"
    ),
}

TUTORIAL_BTN = {
    "uz": ("🤖 Android uchun qo'llanma", "🍏 iPhone uchun qo'llanma"),
    "ru": ("🤖 Инструкция для Android", "🍏 Инструкция для iPhone"),
    "en": ("🤖 Android guide", "🍏 iPhone guide"),
}
RELINK_BTN = {
    "uz": "🔄 Havolani yangilash",
    "ru": "🔄 Обновить ссылку",
    "en": "🔄 Update the link",
}

# Подпись к видео — одинаковая для обеих платформ: видео само показывает шаги.
VIDEO_CAPTION = {
    "uz": {
        "android": "🤖 <b>Android uchun qo'llanma</b>\n\n1️⃣ Havolani <b>fragment.com</b> dan qanday olish\n2️⃣ Sovg'ani profilda qanday ko'rsatish\n\n❗️ Havolani nusxalagach Fragment sahifasini <b>yopmang</b>.\nUlanmasa — /relink bosing va yangi havola yuboring.",
        "ios": "🍏 <b>iPhone uchun qo'llanma</b>\n\n1️⃣ Havolani <b>fragment.com</b> dan qanday olish\n2️⃣ Sovg'ani profilda qanday ko'rsatish\n\nUlanmasa — /relink bosing va yangi havola yuboring.",
    },
    "ru": {
        "android": "🤖 <b>Инструкция для Android</b>\n\n1️⃣ как получить ссылку на <b>fragment.com</b>\n2️⃣ как показать подарок в профиле\n\n❗️ Скопировав ссылку, <b>не закрывайте</b> страницу Fragment.\nНе подключилось — нажмите /relink и пришлите новую ссылку.",
        "ios": "🍏 <b>Инструкция для iPhone</b>\n\n1️⃣ как получить ссылку на <b>fragment.com</b>\n2️⃣ как показать подарок в профиле\n\nНе подключилось — нажмите /relink и пришлите новую ссылку.",
    },
    "en": {
        "android": "🤖 <b>Android guide</b>\n\n1️⃣ how to get the link on <b>fragment.com</b>\n2️⃣ how to display the gift on your profile\n\n❗️ After copying the link, <b>don't close</b> the Fragment page.\nDidn't connect? Tap /relink and send a new link.",
        "ios": "🍏 <b>iPhone guide</b>\n\n1️⃣ how to get the link on <b>fragment.com</b>\n2️⃣ how to display the gift on your profile\n\nDidn't connect? Tap /relink and send a new link.",
    },
}


def _lang(v) -> str:
    return v if v in ("uz", "ru", "en") else "uz"


CANCEL_BTN = {"uz": "Bekor qilish", "ru": "Отмена", "en": "Cancel"}


def tutorial_kb(lang: str, relink_order_id: int | None = None, with_cancel: bool = False):
    """Две кнопки с инструкциями; с relink_order_id — ещё «Обновить ссылку»,
    с with_cancel — «Отмена» (для ожидания новой ссылки)."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    lang = _lang(lang)
    b = InlineKeyboardBuilder()
    b.button(text=TUTORIAL_BTN[lang][0], callback_data="rent:tut:android")
    b.button(text=TUTORIAL_BTN[lang][1], callback_data="rent:tut:ios")
    if relink_order_id:
        b.button(text=RELINK_BTN[lang], callback_data=f"rent:relink:{int(relink_order_id)}")
    if with_cancel:
        b.button(text=CANCEL_BTN[lang], callback_data="rent:relinkcancel")
    b.adjust(1)
    return b.as_markup()


def video_for(platform: str) -> str:
    if platform == "android":
        return config.RENT_VIDEO_ANDROID or config.RENT_VIDEO_IOS
    return config.RENT_VIDEO_IOS


async def send_tutorial_video(bot: Bot, user_id: int, platform: str) -> None:
    """Видео для выбранного телефона. Нет видео или file_id протух — текст."""
    platform = "android" if platform == "android" else "ios"
    lang = _lang(await get_user_language(user_id))
    caption = VIDEO_CAPTION[lang][platform]
    video = video_for(platform)
    if video:
        try:
            await bot.send_video(user_id, video, caption=caption)
            return
        except Exception:
            pass
    await bot.send_message(user_id, caption)


async def send_rent_link_tutorial(bot: Bot, order: dict) -> None:
    """После оплаты аренды: просьба прислать ссылку + выбор инструкции."""
    lang = _lang(await get_user_language(order["user_id"]))
    await bot.send_message(order["user_id"], RENT_LINK_PROMPT[lang], reply_markup=tutorial_kb(lang))
