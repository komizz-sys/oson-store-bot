import re
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from database.db import upsert_user, get_user_orders, get_user_language, set_user_language
from keyboards.user_kb import main_menu_kb, language_select_kb, webapp_reply_kb, subscribe_gate_kb
from services.prices import format_uzs
from services.i18n import t
from services.subscription import is_subscribed

router = Router()

STATUS_KEYS = {
    "awaiting_payment": "status_awaiting_payment",
    "payment_review": "status_payment_review",
    "paid": "status_paid",
    "fulfilling": "status_fulfilling",
    "completed": "status_completed",
    "rejected": "status_rejected",
}


def _strip_custom_emoji(text: str) -> str:
    """Убирает теги анимированных эмодзи, оставляя обычный эмодзи внутри.
    Нужно как запасной вариант: Telegram принимает <tg-emoji> только если у
    ВЛАДЕЛЬЦА бота есть Premium. Если подписки нет (или она кончилась),
    сообщение целиком отклоняется — и без этого отката /start просто
    перестал бы работать."""
    return re.sub(r"<tg-emoji emoji-id='\d+'>(.*?)</tg-emoji>", r"\1", text)


async def _answer_welcome(target, text: str, markup):
    """Пробуем с анимированными эмодзи, при отказе — тем же текстом без них."""
    try:
        await target.answer(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        await target.answer(_strip_custom_emoji(text), reply_markup=markup, disable_web_page_preview=True)


def _welcome_text(lang: str, user) -> str:
    """Приветствие с обращением по имени. Имя оборачиваем в ссылку на
    профиль — так Telegram подсвечивает его, как у крупных магазинов."""
    name = (getattr(user, "first_name", None) or "").strip() or "do'stim"
    safe = name.replace("<", "").replace(">", "").replace("&", "")
    mention = f'<a href="tg://user?id={user.id}">{safe}</a>'
    return t(lang, "welcome").format(name=mention)


async def _show_main_menu(message_or_call_message, user_id: int, user=None):
    lang = await get_user_language(user_id)
    if not lang:
        await message_or_call_message.answer(
            "🌐 Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=language_select_kb(),
        )
        return
    text = _welcome_text(lang, user) if user else t(lang, "welcome").format(name="do'stim")
    await _answer_welcome(message_or_call_message, text, main_menu_kb(lang))
    kb = webapp_reply_kb(lang)
    if kb:
        await message_or_call_message.answer(t(lang, "menu_webapp"), reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await upsert_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name)

    if not await is_subscribed(message.bot, message.from_user.id):
        lang = await get_user_language(message.from_user.id)
        await message.answer(t(lang, "sub_required_text"), reply_markup=subscribe_gate_kb(lang))
        return

    await _show_main_menu(message, message.from_user.id, message.from_user)


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    """Показывает числовой Telegram ID — удобно, чтобы сверить с ADMIN_IDS на Railway."""
    await message.answer(f"🆔 Твой Telegram ID: <code>{message.from_user.id}</code>")


@router.message(Command("ping"))
async def cmd_ping(message: Message):
    """Диагностическая команда — если бот не отвечает на неё, значит на Railway
    запущена не та версия кода, которая сейчас в GitHub/зип-архиве."""
    await message.answer("pong ✅ (deploy check v1)")


@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    if not await is_subscribed(call.bot, call.from_user.id):
        lang = await get_user_language(call.from_user.id)
        await call.answer(t(lang, "sub_still_not"), show_alert=True)
        return

    await call.answer("✅")
    await _show_main_menu(call.message, call.from_user.id, call.from_user)


@router.callback_query(F.data.startswith("setlang:"))
async def set_language(call: CallbackQuery):
    lang = call.data.split(":")[1]
    await set_user_language(call.from_user.id, lang)

    await call.message.edit_text(t(lang, "language_changed"))
    await _answer_welcome(call.message, _welcome_text(lang, call.from_user), main_menu_kb(lang))
    kb = webapp_reply_kb(lang)
    if kb:
        await call.message.answer(t(lang, "menu_webapp"), reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "menu:change_language")
async def change_language(call: CallbackQuery):
    await call.message.edit_text(
        "🌐 Tilni tanlang / Выберите язык / Choose language:",
        reply_markup=language_select_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "menu:back")
async def back_to_menu(call: CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    text = _welcome_text(lang, call.from_user)
    try:
        await call.message.edit_text(text, reply_markup=main_menu_kb(lang), disable_web_page_preview=True)
    except Exception:
        await call.message.edit_text(_strip_custom_emoji(text), reply_markup=main_menu_kb(lang), disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data == "menu:my_orders")
async def my_orders(call: CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    orders = await get_user_orders(call.from_user.id)

    if not orders:
        await call.message.edit_text(t(lang, "my_orders_empty"), reply_markup=main_menu_kb(lang))
        await call.answer()
        return

    lines = [t(lang, "my_orders_header")]
    for o in orders:
        status = t(lang, STATUS_KEYS.get(o["status"], "status_awaiting_payment"))
        lines.append(f"#{o['id']} — {o['item_name']} — {format_uzs(o['price_uzs'])} — {status}")

    await call.message.edit_text("\n".join(lines), reply_markup=main_menu_kb(lang))
    await call.answer()
