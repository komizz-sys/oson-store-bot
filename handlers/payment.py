from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import config
from database.db import attach_payment_proof, get_order
from handlers.states import OrderStates
from keyboards.admin_kb import admin_review_kb
from services.prices import format_uzs

router = Router()


@router.message(OrderStates.waiting_payment_proof, F.photo | F.document)
async def got_payment_proof(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data["order_id"]

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    await attach_payment_proof(order_id, file_id)

    order = await get_order(order_id)

    await message.answer(
        "✅ Чек получен! Заказ отправлен на проверку админу. "
        "Как только оплата подтвердится — мы приступим к выполнению."
    )
    await state.clear()

    caption = (
        f"🆕 <b>Новый чек по заказу #{order_id}</b>\n"
        f"От: @{message.from_user.username or message.from_user.id} (id: {message.from_user.id})\n"
        f"Товар: {order['item_name']}\n"
        f"Получатель: {order['recipient']}\n"
        f"Сумма: {format_uzs(order['price_uzs'])}"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=admin_review_kb(order_id))
            else:
                await bot.send_document(admin_id, file_id, caption=caption, reply_markup=admin_review_kb(order_id))
        except Exception:
            pass


@router.message(OrderStates.waiting_payment_proof)
async def wrong_proof_format(message: Message):
    await message.answer("Пришлите, пожалуйста, скриншот или файл чека об оплате 📎")
