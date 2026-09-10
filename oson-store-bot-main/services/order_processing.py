"""
Общая логика обработки заказа из мини-аппа — используется ДВАЖДЫ:
1) когда данные приходят как web_app_data (через растянутую кнопку клавиатуры
   "Do'konni ochish" — старый путь, sendData() работает только тут);
2) когда данные приходят обычным HTTP POST на /public/create_order (через
   компактную Menu Button "Открыть" у поля ввода — sendData() для неё НЕ
   работает, это ограничение самого Telegram, поэтому мини-апп сам стучится
   на защищённый API с подписью initData, её же использует Tarix/TOP/Profil).

Чтобы не дублировать бизнес-логику (проверка получателя, лимит количества
подарков, расчёт цены аренды) в двух местах, она вынесена сюда один раз —
и старый, и новый путь просто вызывают process_order().
"""

from aiogram import Bot
from aiogram.fsm.context import FSMContext

from handlers.states import OrderStates
from keyboards.user_kb import confirm_order_kb
from services.prices import format_uzs
from services.i18n import t
from database.db import get_user_language, upsert_user


class OrderError(Exception):
    """Ошибка валидации заказа — пользователю уже отправлено сообщение с текстом."""


async def process_order(
    bot: Bot,
    state: FSMContext,
    user_id: int,
    username: str | None,
    full_name: str,
    payload: dict,
) -> None:
    """Валидирует payload из мини-аппа, сохраняет черновик заказа в FSM и
    отправляет пользователю сообщение с подтверждением ("Всё верно?")."""
    await upsert_user(user_id, username or "", full_name)

    category = payload.get("category")
    recipient = (payload.get("recipient") or "").strip()
    recipient_type = payload.get("recipient_type", "friend")

    recipient_user_id = None
    if recipient_type == "self" or not recipient:
        # "Себе" — берём @username с сервера, а не из данных клиента (те
        # иногда не заполнены из-за особенностей кэша WebView).
        if username:
            recipient = "@" + username
        else:
            recipient = ""
        # Мы точно знаем числовой user_id заказчика прямо сейчас — сохраняем
        # его, чтобы при выполнении заказа НЕ искать по @username повторно.
        recipient_user_id = user_id

    if recipient and not recipient.startswith("@"):
        recipient = "@" + recipient
    note = (payload.get("note") or "").strip()

    if not recipient:
        lang = await get_user_language(user_id)
        text = t(lang, "no_username_error")
        await bot.send_message(user_id, text)
        raise OrderError(text)

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
        await bot.send_message(
            user_id,
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
            text = "Некорректные данные заказа аренды. Откройте магазин заново."
            await bot.send_message(user_id, text)
            raise OrderError(text)

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
        await bot.send_message(
            user_id,
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
        text = "Неизвестный тип заказа из мини-аппа."
        await bot.send_message(user_id, text)
        raise OrderError(text)
