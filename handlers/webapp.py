import json

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from services.order_processing import process_order, OrderError

router = Router()


@router.message(F.web_app_data)
async def handle_web_app_data(message: Message, state: FSMContext):
    try:
        payload = json.loads(message.web_app_data.data)
    except Exception:
        await message.answer("Не удалось прочитать выбор из магазина, попробуйте ещё раз через /start.")
        return

    try:
        await process_order(
            bot=message.bot,
            state=state,
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            payload=payload,
        )
    except OrderError:
        pass  # текст ошибки уже отправлен пользователю внутри process_order
