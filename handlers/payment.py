import asyncio

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import config
from database.db import (
    attach_payment_proof, get_order, set_order_status,
    attach_cart_payment_proof, get_cart_orders, set_cart_status,
)
from handlers.states import OrderStates
from keyboards.admin_kb import admin_review_kb, admin_review_cart_kb
from services.prices import format_uzs
from services.i18n import t
from database.db import get_user_language

router = Router()

REMINDER_DELAY_SECONDS = 20 * 60


async def _remind_admin_if_still_pending(bot: Bot, order_id: int, cart_id: str | None = None) -> None:
    """Через 20 минут после чека — если админ так и не нажал Подтвердить/Отклонить,
    напоминаем ещё раз. Тихо ничего не делает, если заказ уже обработан."""
    await asyncio.sleep(REMINDER_DELAY_SECONDS)

    order = await get_order(order_id)
    if not order or order["status"] != "payment_review":
        return  # уже подтверждён/отклонён — напоминание не нужно

    if cart_id:
        cart_orders = await get_cart_orders(cart_id)
        total = sum(o["price_uzs"] for o in cart_orders)
        text = (
            f"⏰ Напоминание: корзина {cart_id} ({len(cart_orders)} тов.) "
            f"ждёт решения уже 20 минут.\n"
            f"Итого: {format_uzs(total)}\n\n"
            "Подтверди или отклони оплату кнопками под чеком выше ⬆️"
        )
    else:
        text = (
            f"⏰ Напоминание: заказ #{order_id} ждёт решения уже 20 минут.\n"
            f"Товар: {order['item_name']}\n"
            f"Получатель: {order['recipient']}\n"
            f"Сумма: {format_uzs(order['price_uzs'])}\n\n"
            "Подтверди или отклони оплату кнопками под чеком выше ⬆️"
        )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


@router.callback_query(F.data == "pay:manual")
async def pay_manual_ack(call: CallbackQuery):
    # Кнопка просто подтверждает готовность оплатить — саму загрузку чека
    # обрабатывает handler ниже (он срабатывает на любое фото/документ в этом состоянии).
    await call.answer("Жду скриншот или файл чека 📎", show_alert=False)


@router.callback_query(F.data == "order:cancel")
async def cancel_at_payment_step(call: CallbackQuery, state: FSMContext):
    """
    Отмена на шаге оплаты (после того как заказ уже создан).
    Отмену на шаге ПОДТВЕРЖДЕНИЯ заказа (до его создания) обрабатывает
    order.py — он стоит раньше в цепочке роутеров и ловит "order:cancel"
    только в состоянии OrderStates.confirming. Этот handler подхватывает
    все остальные случаи (когда заказ уже создан и ждём чек).
    """
    data = await state.get_data()
    order_id = data.get("order_id")
    cart_id = data.get("cart_id")

    try:
        if cart_id:
            # Корзина оплачивается одной суммой — и отменяется тоже целиком
            await set_cart_status(cart_id, "rejected", "Отменено пользователем")
        elif order_id:
            await set_order_status(order_id, "rejected", admin_comment="Отменено пользователем")
    except Exception:
        pass

    await state.clear()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer("❌ Заказ отменён. Наберите /start, чтобы начать заново.")
    await call.answer()


@router.message(OrderStates.waiting_payment_proof, F.photo | F.document)
async def got_payment_proof(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    cart_id = data.get("cart_id")

    if not order_id and not cart_id:
        await message.answer("Не нашёл номер заказа. Начните заново через /start.")
        await state.clear()
        return

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    lang = await get_user_language(message.from_user.id)
    sender = f"@{message.from_user.username or message.from_user.id} (id: {message.from_user.id})"

    if cart_id:
        # Один чек на всю корзину: помечаем все её товары и отправляем админу
        # ОДНО сообщение с общей суммой и одной парой кнопок.
        await attach_cart_payment_proof(cart_id, file_id)
        cart_orders = await get_cart_orders(cart_id)
        total = sum(o["price_uzs"] for o in cart_orders)
        items = "\n".join(f"  • {o['item_name']} → {o['recipient']}" for o in cart_orders)
        caption = (
            f"🛒 <b>Новый чек по корзине {cart_id}</b> ({len(cart_orders)} тов.)\n"
            f"От: {sender}\n"
            f"{items}\n"
            f"Итого: {format_uzs(total)}"
        )
        markup = admin_review_cart_kb(cart_id)
        remind_id = cart_orders[0]["id"] if cart_orders else None
    else:
        await attach_payment_proof(order_id, file_id)
        order = await get_order(order_id)
        caption = (
            f"🆕 <b>Новый чек по заказу #{order_id}</b>\n"
            f"От: {sender}\n"
            f"Товар: {order['item_name'] if order else '—'}\n"
            f"Получатель: {order['recipient'] if order else '—'}\n"
            f"Сумма: {format_uzs(order['price_uzs']) if order else '—'}"
        )
        markup = admin_review_kb(order_id)
        remind_id = order_id

    await message.answer(t(lang, "proof_received"))
    await state.clear()

    for admin_id in config.ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=markup)
            else:
                await bot.send_document(admin_id, file_id, caption=caption, reply_markup=markup)
        except Exception:
            pass

    if remind_id:
        asyncio.create_task(_remind_admin_if_still_pending(bot, remind_id, cart_id))


@router.message(OrderStates.waiting_payment_proof, F.text == "/start")
async def handle_start_in_state(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню обновлено. Введите /start ещё раз.")


@router.message(OrderStates.waiting_payment_proof)
async def wrong_proof_format(message: Message):
    await message.answer("Пришлите, пожалуйста, скриншот или файл чека об оплате 📎 (или нажмите «Отмена» выше)")
