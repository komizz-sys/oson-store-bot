import json

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handlers.states import OrderStates
from keyboards.user_kb import confirm_order_kb
from services.prices import format_uzs
from services.i18n import t
from database.db import get_user_language

router = Router()

# Для категорий, у которых есть дополнительный контент (видео, текст и т.д.)
CATEGORY_CONTENT = {
    "nft_rent": {
        "video": None,  # Заполняется при создании заказа
        "text": None,    # Может быть инструкция по использованию
    }
}


@router.message(F.web_app_data)
async def handle_web_app_data(message: Message, state: FSMContext):
    try:
        payload = json.loads(message.web_app_data.data)
    except Exception:
        await message.answer("Не удалось прочитать выбор из магазина, попробуйте ещё раз через /start.")
        return

    category = payload.get("category")
    recipient = (payload.get("recipient") or "").strip()
    recipient_type = payload.get("recipient_type", "friend")

    recipient_user_id = None
    if recipient_type == "self" or not recipient:
        # "Себе" — берём @username с сервера (message.from_user всегда точен,
        # в отличие от tg.initDataUnsafe на клиенте, который иногда не заполнен)
        if message.from_user.username:
            recipient = "@" + message.from_user.username
        else:
            recipient = ""
        # Мы точно знаем числовой user_id заказчика прямо сейчас — сохраняем
        # его, чтобы при выполнении заказа НЕ искать по @username повторно
        # (такой повторный поиск через bot.get_chat может не сработать).
        recipient_user_id = message.from_user.id

    if recipient and not recipient.startswith("@"):
        recipient = "@" + recipient
    note = (payload.get("note") or "").strip()

    if not recipient:
        lang = await get_user_language(message.from_user.id)
        await message.answer(t(lang, "no_username_error"))
        return

    if category in ("stars", "stars_custom", "premium", "simple_gift"):
        data = {
            "category": category if category != "stars_custom" else "stars",
            "item_name": payload["item_name"],
            "price": payload["price"],
            "quantity": payload.get("quantity", 1),
            "recipient": recipient,
        }
        if category == "simple_gift":
            data["nft_address"] = payload["gift_id"]  # переиспользуем поле под gift_id
            # Защита от накрутки количества мимо интерфейса (в магазине максимум 10)
            qty = max(1, min(int(data["quantity"] or 1), 10))
            if qty != data["quantity"]:
                unit_price = payload["price"] / max(int(payload.get("quantity", 1) or 1), 1)
                data["price"] = round(unit_price * qty)
            data["quantity"] = qty
        if recipient_user_id:
            data["recipient_user_id"] = recipient_user_id

        await state.update_data(**data, note=note)
        await state.set_state(OrderStates.confirming)

        note_line = f"\nЗаметка: {note}" if note else ""
        await message.answer(
            f"Проверьте заказ:\n\n"
            f"Товар: <b>{data['item_name']}</b>\n"
            f"Получатель: {recipient}{note_line}\n"
            f"Сумма к оплате: <b>{format_uzs(data['price'])}</b>\n\n"
            "Всё верно?",
            reply_markup=confirm_order_kb(),
        )

    elif category == "nft_rent":
        from services.marketapp_service import calc_rent_price

        try:
            days = int(payload["days"])
            base_price_per_day_gram = float(payload["base_price_per_day_gram"])
        except (KeyError, ValueError, TypeError):
            await message.answer("Некорректные данные заказа аренды. Откройте магазин заново.")
            return

        calc = calc_rent_price(base_price_per_day_gram, days)

        await state.update_data(
            category="nft_rent",
            item_name=payload["item_name"],
            nft_address=payload["nft_address"],
            base_price_per_day_gram=base_price_per_day_gram,
            rent_days=days,
            price=calc["total_to_pay"],
            quantity=1,
            recipient=recipient,
            recipient_user_id=recipient_user_id,
            note=note,
        )
        await state.set_state(OrderStates.confirming)

        note_line = f"\nЗаметка: {note}" if note else ""
        await message.answer(
            f"Проверьте заказ:\n\n"
            f"Товар: <b>Аренда «{payload['item_name']}» на {days} дн.</b>\n"
            f"Получатель: {recipient}{note_line}\n"
            f"Комиссия сети: {format_uzs(calc['fee_total_uzs'])} "
            f"(вернётся вам после аренды: {format_uzs(calc['fee_refundable_uzs'])})\n"
            f"Сумма к оплате: <b>{format_uzs(calc['total_to_pay'])}</b>\n\n"
            "Всё верно?",
            reply_markup=confirm_order_kb(),
        )
    else:
        await message.answer("Неизвестный тип заказа из мини-аппа.")
