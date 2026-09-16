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
from aiogram.types import Message

import config
from database.db import get_pending_rent_link_order, set_rent_link, get_user_language
from services import marketapp_api

router = Router()

# Реальная ссылка, которую Fragment выдаёт для подключения арендованного
# гифта, — это TonConnect-ссылка вида "tc://?v=2&id=...&r=..." (у каждого
# клиента своя, но префикс всегда tc://). На всякий случай также принимаем
# обычные https:// и t.me/ — вдруг Fragment когда-нибудь поменяет формат.
_LINK_RE = re.compile(r"^(tc://\S+|https?://\S+|t\.me/\S+)$", re.IGNORECASE)

# Тексты на 3 языках — показываем на языке, выбранном клиентом при /start.
CONNECTING = {
    "uz": "⏳ Havolangiz qabul qilindi, sovg'ani ulayapman...",
    "ru": "⏳ Ссылку получил, подключаю подарок...",
    "en": "⏳ Got your link, connecting the gift...",
}
SUCCESS = {
    "uz": "✅ Tayyor! «{item}» sovg'asi profilingizga ulandi.\n\nTelegram profilingizni oching va tekshiring — sovg'a ko'rinishi kerak. Agar darhol ko'rinmasa, Telegram'ni qayta ishga tushiring.",
    "ru": "✅ Готово! Подарок «{item}» подключён к вашему профилю.\n\nОткройте свой профиль в Telegram и проверьте — подарок должен отображаться. Если не видно сразу, перезапустите Telegram.",
    "en": "✅ Done! The gift \"{item}\" is connected to your profile.\n\nOpen your Telegram profile to check — the gift should be visible. If not, restart Telegram.",
}
FAILED = {
    "uz": "⚠️ Sovg'ani ulashda xatolik yuz berdi. Operator tez orada qo'lda ulab beradi — biroz kuting.",
    "ru": "⚠️ При подключении подарка произошла ошибка. Оператор скоро подключит вручную — немного подождите.",
    "en": "⚠️ Something went wrong while connecting the gift. An operator will connect it manually shortly.",
}


def _lang(value: str | None) -> str:
    return value if value in ("uz", "ru", "en") else "uz"


@router.message(F.text)
async def receive_rent_link(message: Message, bot: Bot):
    link = (message.text or "").strip()
    if not _LINK_RE.match(link):
        raise SkipHandler  # не похоже на ссылку — не наш случай

    order = await get_pending_rent_link_order(message.from_user.id)
    if not order:
        raise SkipHandler  # не наш случай — пусть сообщение обработает другой хендлер

    lang = _lang(await get_user_language(message.from_user.id))
    await set_rent_link(order["id"], link)
    await message.answer(CONNECTING[lang])

    # Пытаемся подключить автоматически. Если marketapp вернёт ошибку — не
    # бросаем клиента: честно говорим, что подключит оператор, и зовём админа
    # (ссылка уже сохранена в заказе, так что ничего не потеряется).
    try:
        await marketapp_api.rent_connect_tonconnect(order["nft_address"], link)
    except Exception as e:
        await message.answer(FAILED[lang])
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ Заказ #{order['id']} ({order['item_name']}) — АВТОподключение аренды "
                    f"не удалось: {e}\n\nСсылка клиента:\n<code>{link}</code>\n\n"
                    "Подключи вручную на marketapp.org, затем нажми «Заказ выполнен».",
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
        return

    await message.answer(SUCCESS[lang].format(item=order["item_name"]))
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ Заказ #{order['id']} ({order['item_name']}) — аренда подключена "
                f"АВТОМАТИЧЕСКИ клиенту {order['recipient']}. Вручную ничего делать не нужно.",
                disable_web_page_preview=True,
            )
        except Exception:
            pass
