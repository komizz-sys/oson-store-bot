from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import config
from database.db import attach_payment_proof, get_order, update_order_status
from handlers.states import OrderStates
from keyboards.admin_kb import admin_review_kb
from services.prices import format_uzs

router = Router()


# 1. Обработка кнопки "Отмена"
@router.callback_query(F.data.startswith("cancel_") | (F.data == "cancel_order") | (F.data == "cancel"))
async def cancel_order_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Заказ отменен")
    
    data = await state.get_data()
    order_id = data.get("order_id")
    
    parts = callback.data.split("_")
    if len(parts) > 1 and parts[-1].isdigit():
        order_id = int(parts[-1])
        
    if order_id:
        try:
            await update_order_status(order_id, "cancelled")
        except Exception:
            pass

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Заказ отменен. Вы можете начать заново с помощью команды /start")


# 2. Обработка кнопки "Оплатить и прислать чек"
@router.callback_query(F.data.startswith("pay_") | F.data.startswith("order_pay_") | (F.data == "pay_check") | (F.data == "send_receipt"))
async def start_payment_proof(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    parts = callback.data.split("_")
    if len(parts) > 1 and parts[-1].isdigit():
        await state.update_data(order_id=int(parts[-1]))
    
    await state.set_state(OrderStates.waiting_payment_proof)
    await callback.message.answer(
        "🧾 Пожалуйста, отправьте скриншот или файл чека об оплате:"
    )


# 3. Получение фото или файла чека
@router.message(OrderStates.waiting_payment_proof, F.photo | F.document)
async def got_payment_proof(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await message.answer("Ошибка: номер заказа не найден. Попробуйте оформить заказ заново через /start.")
        await state.clear()
        return

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


# 4. Сброс состояния, если пользователь ввел /start
@router.message(OrderStates.waiting_payment_proof, F.text == "/start")
async def handle_start_in_state(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню обновлено. Введите /start еще раз.")


# 5. Обработка любого неподходящего текста
@router.message(OrderStates.waiting_payment_proof)
async def wrong_proof_format(message: Message):
    await message.answer("Пришлите, пожалуйста, скриншот или файл чека об оплате 📎 (или нажмите /start для отмены)")
