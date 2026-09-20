"""
Подтверждение и оплата КОРЗИНЫ в чате бота.

Сценарий тот же, что у одиночного заказа, просто товаров несколько:
мини-апп присылает корзину -> бот показывает список и общую сумму ->
клиент жмёт «Подтвердить» -> создаются заказы (все с одним cart_id) и
показываются реквизиты с ОДНОЙ суммой -> клиент присылает один чек.
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import config
from database.db import get_user_language
from handlers.states import OrderStates
from keyboards.user_kb import payment_methods_kb
from services.cart import create_cart_orders, summary_text
from services.order_processing import too_many_pending
from services.i18n import t
from services.prices import format_uzs

router = Router()


@router.callback_query(F.data == "cart:cancel", OrderStates.confirming_cart)
async def cancel_cart(call: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_user_language(call.from_user.id)
    await call.message.edit_text(t(lang, "cart_cancelled"))
    await call.answer()


@router.callback_query(F.data == "cart:confirm", OrderStates.confirming_cart)
async def confirm_cart(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rows = data.get("cart_rows") or []
    if not rows:
        await call.answer("Корзина пуста — откройте магазин заново", show_alert=True)
        await state.clear()
        return

    lang = await get_user_language(call.from_user.id)

    # Тот же лимит висящих заказов, что и в витрине — см. order_processing.
    if await too_many_pending(call.from_user.id):
        await call.answer(t(lang, "too_many_pending"), show_alert=True)
        return

    created = await create_cart_orders(rows, call.from_user.id, call.from_user.username)

    # Дальше — обычный шаг оплаты: тот же state и тот же обработчик чека, что и
    # у одиночного заказа, просто в данных лежит ещё и cart_id.
    await state.update_data(
        cart_id=created["cart_id"],
        order_id=created["order_ids"][0],
        cart_order_ids=created["order_ids"],
    )
    await state.set_state(OrderStates.waiting_payment_proof)

    amount_note = ""
    if config.UNIQUE_AMOUNT_ENABLED and created["pay_amount"] != created["total"]:
        amount_note = (
            f"\n\n⚠️ {t(lang, 'cart_exact_amount')} <b>{format_uzs(created['pay_amount'])}</b>"
            + t(lang, "pay_commission_note")
        )

    await call.message.edit_text(
        f"🛒 <b>{t(lang, 'cart_created_title')}</b>\n\n"
        f"{summary_text(rows, lang)}\n\n"
        f"{t(lang, 'order_check_total')}: <b>{format_uzs(created['total'])}</b>\n\n"
        + t(lang, "order_pay_card")
        + f"<code>{config.PAYMENT_CARD_NUMBER}</code>\n"
        + f"{t(lang, 'order_pay_receiver')}: {config.PAYMENT_CARD_HOLDER}"
        + amount_note
        + "\n"
        + t(lang, "order_pay_hint"),
        reply_markup=payment_methods_kb(),
    )
    await call.answer()

# Отмену на шаге оплаты (когда заказы корзины уже созданы) обрабатывает
# handlers/payment.py — там один обработчик на все виды заказов, он сам видит
# cart_id в состоянии и снимает всю корзину целиком.
