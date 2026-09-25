"""
Ссылка для подключения арендованного подарка — всё, что клиент делает в чате:

- присылает tc://-ссылку (первую после оплаты или новую взамен умершей);
- жмёт «Обновить ссылку» / /relink, чтобы переподключить действующую аренду;
- выбирает видео-инструкцию для своего телефона (Android или iPhone).

Само подключение — services/rent_connect.py, общее с витриной.

Регистрируется ПОСЛЕДНИМ в bot.py: голую ссылку ловим, только если у клиента
есть аренда, к которой её можно применить, иначе пропускаем дальше.
"""

import html
import re
import time

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_user_language
from services.rent_connect import relink_rental, relinkable_rentals, submit_rent_link
from services.rent_link import send_tutorial_video, tutorial_kb

router = Router()

# Реальная ссылка Fragment — TonConnect вида "tc://?v=2&id=...&r=...". На всякий
# случай принимаем и https:// / t.me/ — вдруг формат поменяется.
_LINK_RE = re.compile(r"^(tc://\S+|https?://\S+|t\.me/\S+)$", re.IGNORECASE)

RELINK_WINDOW_SEC = 30 * 60   # столько ждём новую ссылку после «Обновить ссылку»

_lang = lambda v: v if v in ("uz", "ru", "en") else "uz"

ASK_LINK = {
    "uz": ("🔄 <b>{item}</b> — yangi havola yuboring.\n\n"
           "1️⃣ fragment.com da yangi havola oling\n"
           "2️⃣ Shu yerga yuboring 👇\n\n"
           "❗️ Havolani nusxalagach Fragment sahifasini <b>yopmang</b> — ulanish o'sha sahifada ko'rinadi."),
    "ru": ("🔄 <b>{item}</b> — пришлите новую ссылку.\n\n"
           "1️⃣ Возьмите новую ссылку на fragment.com\n"
           "2️⃣ Отправьте её сюда 👇\n\n"
           "❗️ Скопировав ссылку, <b>не закрывайте</b> страницу Fragment — подключение появится именно на ней."),
    "en": ("🔄 <b>{item}</b> — send a new link.\n\n"
           "1️⃣ Get a new link on fragment.com\n"
           "2️⃣ Send it here 👇\n\n"
           "❗️ After copying the link, <b>don't close</b> the Fragment page — the connection shows up on that page."),
}
PICK_RENTAL = {
    "uz": "Qaysi sovg'a uchun havolani yangilaymiz?",
    "ru": "Для какого подарка обновить ссылку?",
    "en": "Which gift should the link be updated for?",
}
NO_RENTAL = {
    "uz": "Sizda faol ijara yo'q.",
    "ru": "У вас нет действующей аренды.",
    "en": "You have no active rentals.",
}
NOT_A_LINK = {
    "uz": "Bu havolaga o'xshamaydi. Fragment'dagi <code>tc://</code> bilan boshlanadigan havolani yuboring.",
    "ru": "Это не похоже на ссылку. Пришлите ссылку с Fragment, которая начинается с <code>tc://</code>.",
    "en": "That doesn't look like a link. Send the Fragment link that starts with <code>tc://</code>.",
}
RELINK_FAILED = {
    "uz": "Bu ijara tugagan yoki topilmadi.",
    "ru": "Эта аренда закончилась или не найдена.",
    "en": "This rental has ended or wasn't found.",
}
CANCELLED = {"uz": "Bekor qilindi.", "ru": "Отменено.", "en": "Cancelled."}


class RelinkStates(StatesGroup):
    waiting_link = State()


def _pick_kb(rentals: list[dict]):
    b = InlineKeyboardBuilder()
    for r in rentals[:10]:
        b.button(text=f"🖼 {r['item_name']}"[:60], callback_data=f"rent:relink:{int(r['order_id'])}")
    b.adjust(1)
    return b.as_markup()


async def _start_relink(bot: Bot, user_id: int, order_id: int, item_name: str, state: FSMContext):
    lang = _lang(await get_user_language(user_id))
    await state.set_state(RelinkStates.waiting_link)
    await state.update_data(relink_order_id=order_id, relink_at=time.time())
    await bot.send_message(user_id, ASK_LINK[lang].format(item=html.escape(item_name or "")),
                           reply_markup=tutorial_kb(lang, with_cancel=True))


# ---------------------------------------------------------------- кнопки

@router.callback_query(F.data.startswith("rent:tut:"))
async def on_tutorial(call: CallbackQuery, bot: Bot):
    platform = call.data.split(":")[2]
    await call.answer()
    await send_tutorial_video(bot, call.from_user.id, platform)


@router.callback_query(F.data == "rent:displayhelp")
async def on_old_display_button(call: CallbackQuery, bot: Bot):
    """Кнопка из старых сообщений — теперь предлагает выбрать телефон."""
    lang = _lang(await get_user_language(call.from_user.id))
    await call.answer()
    from services.rent_link import RENT_LINK_PROMPT
    await bot.send_message(call.from_user.id, RENT_LINK_PROMPT[lang], reply_markup=tutorial_kb(lang))


@router.callback_query(F.data.startswith("rent:relink:"))
async def on_relink_button(call: CallbackQuery, state: FSMContext, bot: Bot):
    lang = _lang(await get_user_language(call.from_user.id))
    try:
        order_id = int(call.data.split(":")[2])
    except ValueError:
        await call.answer()
        return
    rental = next((r for r in await relinkable_rentals(call.from_user.id) if r["order_id"] == order_id), None)
    if not rental:
        await call.answer(RELINK_FAILED[lang], show_alert=True)
        return
    await call.answer()
    await _start_relink(bot, call.from_user.id, order_id, rental["item_name"], state)


@router.callback_query(F.data == "rent:relinkcancel")
async def on_relink_cancel(call: CallbackQuery, state: FSMContext):
    lang = _lang(await get_user_language(call.from_user.id))
    await state.clear()
    await call.answer(CANCELLED[lang])
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.message(Command("relink"))
async def cmd_relink(message: Message, state: FSMContext, bot: Bot):
    lang = _lang(await get_user_language(message.from_user.id))
    rentals = await relinkable_rentals(message.from_user.id)
    if not rentals:
        await message.answer(NO_RENTAL[lang])
        return
    if len(rentals) == 1:
        await _start_relink(bot, message.from_user.id, rentals[0]["order_id"], rentals[0]["item_name"], state)
        return
    await message.answer(PICK_RENTAL[lang], reply_markup=_pick_kb(rentals))


# ---------------------------------------------------------------- ссылка

@router.message(RelinkStates.waiting_link, F.text)
async def on_relink_link(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    if text.startswith("/"):
        await state.clear()
        raise SkipHandler
    data = await state.get_data()
    lang = _lang(await get_user_language(message.from_user.id))
    if time.time() - float(data.get("relink_at") or 0) > RELINK_WINDOW_SEC:
        await state.clear()
        raise SkipHandler
    if not _LINK_RE.match(text):
        await message.answer(NOT_A_LINK[lang])
        return  # остаёмся в ожидании ссылки
    await state.clear()
    result = await relink_rental(bot, message.from_user.id, int(data.get("relink_order_id") or 0), text)
    if result is None:
        await message.answer(RELINK_FAILED[lang])


@router.message(F.text)
async def receive_rent_link(message: Message, bot: Bot):
    link = (message.text or "").strip()
    if not _LINK_RE.match(link):
        raise SkipHandler  # не похоже на ссылку — не наш случай

    # Первая ссылка или новая взамен умершей — решает submit_rent_link.
    result = await submit_rent_link(bot, message.from_user.id, link)
    if result is None:
        raise SkipHandler  # нет подходящей аренды — ссылка не нам
    if result.get("choose"):
        lang = _lang(await get_user_language(message.from_user.id))
        await message.answer(PICK_RENTAL[lang], reply_markup=_pick_kb(result["choose"]))
