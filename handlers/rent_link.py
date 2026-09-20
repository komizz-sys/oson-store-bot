"""
Ловит ссылку, которую клиент присылает В ОТВЕТ на видео-инструкцию по аренде
(см. services/rent_link.py), и САМ подключает арендованный подарок к его
профилю через marketapp API (POST /v1/rent/{nft_address}/tonconnect/).

Раньше это делалось вручную: клиент присылал tc://-ссылку, админ шёл на
marketapp.org, вставлял её в поле "TON Connect Link" и жал Connect. Теперь
всё то же самое делает бот — админ получает только уведомление о результате.

Регистрируется ПОСЛЕДНИМ в bot.py — если у пользователя нет ни одного заказа
аренды, ожидающего ссылку, пропускаем сообщение дальше (SkipHandler), чтобы
не перехватывать чужие ссылки, отправленные для других целей.
"""

import re

from aiogram import Router, F, Bot
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import CallbackQuery, Message

from database.db import get_pending_rent_link_order, set_rent_link, get_user_language
from services.rent_connect import connect_rent_link

router = Router()

# Реальная ссылка, которую Fragment выдаёт для подключения арендованного
# гифта, — это TonConnect-ссылка вида "tc://?v=2&id=...&r=..." (у каждого
# клиента своя, но префикс всегда tc://). На всякий случай также принимаем
# обычные https:// и t.me/ — вдруг Fragment когда-нибудь поменяет формат.
_LINK_RE = re.compile(r"^(tc://\S+|https?://\S+|t\.me/\S+)$", re.IGNORECASE)

# Тексты для клиента (CONNECTING/SUCCESS/PENDING/FAILED) живут в
# services/rent_connect.py — там же, где сама логика подключения, чтобы из
# витрины и из чата человек видел одно и то же.


@router.message(F.text)
async def receive_rent_link(message: Message, bot: Bot):
    link = (message.text or "").strip()
    if not _LINK_RE.match(link):
        raise SkipHandler  # не похоже на ссылку — не наш случай

    order = await get_pending_rent_link_order(message.from_user.id)
    if not order:
        raise SkipHandler  # не наш случай — пусть сообщение обработает другой хендлер

    await set_rent_link(order["id"], link)

    # Само подключение (и повторы при неудаче) живёт в services/rent_connect.py —
    # общем для этого обработчика и для витрины, чтобы клиент получал одни и те
    # же сообщения независимо от того, куда он прислал ссылку.
    await connect_rent_link(bot, order, link)


@router.callback_query(F.data == "rent:displayhelp")
async def send_display_help(call: CallbackQuery, bot: Bot):
    """
    Инструкция «как показать подарок в профиле» — видео, если оно записано,
    иначе тот же текст сообщением.

    Включить показ за клиента бот не может: подарок лежит на его аккаунте
    Fragment, и это действие внутри его аккаунта. Единственное, что в наших
    силах — объяснить максимально коротко и показать пальцем.
    """
    import config
    from services.rent_connect import DISPLAY_HELP, _lang_fallback

    lang = _lang_fallback(await get_user_language(call.from_user.id))
    caption = DISPLAY_HELP[lang]

    try:
        if config.RENT_DISPLAY_VIDEO:
            await bot.send_video(call.from_user.id, config.RENT_DISPLAY_VIDEO, caption=caption)
        else:
            await bot.send_message(call.from_user.id, caption)
        await call.answer()
    except Exception:
        # file_id протух или переменная заполнена не тем — текст всё равно
        # должен дойти, иначе кнопка просто молчит.
        try:
            await bot.send_message(call.from_user.id, caption)
            await call.answer()
        except Exception:
            await call.answer("Xatolik / Ошибка", show_alert=True)
