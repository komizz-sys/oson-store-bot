"""
Ловит ссылку, которую клиент присылает В ОТВЕТ на видео-инструкцию по аренде
(см. services/rent_link.py). Привязывает её к конкретному оплаченному заказу
аренды (а не просто шлёт админу "какое-то сообщение от какого-то юзера"),
чтобы не путаться, если заказов много.

Регистрируется ПОСЛЕДНИМ в bot.py — если у пользователя нет ни одного заказа
аренды, ожидающего ссылку, пропускаем сообщение дальше (SkipHandler), чтобы
не перехватывать чужие ссылки, отправленные для других целей.
"""

import re

from aiogram import Router, F, Bot
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message

import config
from database.db import get_pending_rent_link_order, set_rent_link

router = Router()

# Реальная ссылка, которую Fragment выдаёт для подключения арендованного
# гифта, — это TonConnect-ссылка вида "tc://?v=2&id=...&r=..." (у каждого
# клиента своя, но префикс всегда tc://). На всякий случай также принимаем
# обычные https:// и t.me/ — вдруг Fragment когда-нибудь поменяет формат.
_LINK_RE = re.compile(r"^(tc://\S+|https?://\S+|t\.me/\S+)$", re.IGNORECASE)


@router.message(F.text)
async def receive_rent_link(message: Message, bot: Bot):
    link = (message.text or "").strip()
    if not _LINK_RE.match(link):
        raise SkipHandler  # не похоже на ссылку — не наш случай[cite: 6]

    order = await get_pending_rent_link_order(message.from_user.id)
    if not order:
        raise SkipHandler  # не наш случай — пусть сообщение обработает другой хендлер[cite: 6]

    await set_rent_link(order["id"], link)
    await message.answer(
        f"✅ Ссылку получил! Как только подключу подарок «{order['item_name']}» "
        "(заказ #" + str(order["id"]) + ") — сразу напишу сюда."
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔗 Заказ #{order['id']} ({order['item_name']}) — клиент прислал ссылку "
                f"для подключения аренды:\n{link}\n\n"
                "Подключи гифт на marketapp.org на эту ссылку, затем нажми «Заказ выполнен» "
                "под чеком этого заказа.",
                disable_web_page_preview=True,
            )
        except Exception:
            pass  #[cite: 6]
