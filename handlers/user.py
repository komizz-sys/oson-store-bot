from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from database.db import upsert_user, get_user_orders, get_user_language, set_user_language
from keyboards.user_kb import main_menu_kb, language_select_kb
from services.prices import format_uzs
from services.i18n import t

router = Router()

STATUS_KEYS = {
    "awaiting_payment": "status_awaiting_payment",
    "payment_review": "status_payment_review",
    "paid": "status_paid",
    "fulfilling": "status_fulfilling",
    "completed": "status_completed",
    "rejected": "status_rejected",
}


@router.message(CommandStart())
async def cmd_start(message: Message):
    await upsert_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name)

    lang = await get_user_language(message.from_user.id)
    if not lang:
        # Новый пользователь (или ещё не выбирал язык) — сначала спрашиваем язык
        await message.answer(
            "🌐 Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=language_select_kb(),
        )
        return

    await message.answer(t(lang, "welcome"), reply_markup=main_menu_kb(lang))


@router.callback_query(F.data.startswith("setlang:"))
async def set_language(call: CallbackQuery):
    lang = call.data.split(":")[1]
    await set_user_language(call.from_user.id, lang)

    await call.message.edit_text(t(lang, "language_changed"))
    await call.message.answer(t(lang, "welcome"), reply_markup=main_menu_kb(lang))
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
    await call.message.edit_text(t(lang, "welcome"), reply_markup=main_menu_kb(lang))
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
