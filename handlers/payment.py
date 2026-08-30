from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import config
from database.db import attach_payment_proof, get_order, set_order_status
from handlers.states import OrderStates
from keyboards.admin_kb import admin_review_kb
from services.prices import format_uzs
from services.i18n import t
from database.db import get_user_language

router = Router()


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

    if order_id:
        try:
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

    if not order_id:
        await message.answer("Не нашёл номер заказа. Начните заново через /start.")
        await state.clear()
        return

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    await attach_payment_proof(order_id, file_id)

    order = await get_order(order_id)
    lang = await get_user_language(message.from_user.id)

    await message.answer(t(lang, "proof_received"))
    await state.clear()

    caption = (
        f"🆕 <b>Новый чек по заказу #{order_id}</b>\n"
        f"От: @{message.from_user.username or message.from_user.id} (id: {message.from_user.id})\n"
        f"Товар: {order['item_name'] if order else '—'}\n"
        f"Получатель: {order['recipient'] if order else '—'}\n"
        f"Сумма: {format_uzs(order['price_uzs']) if order else '—'}"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=admin_review_kb(order_id))
            else:
                await bot.send_document(admin_id, file_id, caption=caption, reply_markup=admin_review_kb(order_id))
        except Exception:
            pass


@router.message(OrderStates.waiting_payment_proof, F.text == "/start")
async def handle_start_in_state(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню обновлено. Введите /start ещё раз.")


@router.message(OrderStates.waiting_payment_proof)
async def wrong_proof_format(message: Message):
    await message.answer("Пришлите, пожалуйста, скриншот или файл чека об оплате 📎 (или нажмите «Отмена» выше)")
