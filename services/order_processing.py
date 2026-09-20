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
from services.prices import format_uzs, STARS_MIN, STARS_MAX
from services.i18n import t
from database.db import get_user_language, upsert_user


class OrderError(Exception):
    """Ошибка валидации заказа — пользователю уже отправлено сообщение с текстом."""


# Сколько незакрытых заказов клиент может держать одновременно. Смысл не в
# недоверии, а в том, что десять висящих заявок от одного человека — это
# всегда либо случайные повторы, либо попытка завалить админа. Оплатил или
# отменил предыдущие — оформляй сколько угодно новых.
MAX_PENDING_ORDERS_PER_USER = 3


def wants_exact_price(category: str, item_name: str) -> bool:
    """
    Этому товару надбавку к сумме НЕ даём — платят ровно цену.

    Нужно для позиций, которые владелец закупает вручную (Premium на 1 месяц):
    автоподтверждение по SMS для них всё равно не используется, а «странная»
    сумма 49 206 вместо ровных 49 000 только путает покупателя.

    Помечается флагом "exact_price": true у тарифа в data/prices.json —
    чтобы поменять решение можно было в прайсе, не трогая код.
    """
    if category != "premium":
        return False
    from services.prices import get_premium_packages

    try:
        for pkg in get_premium_packages():
            if not pkg.get("exact_price"):
                continue
            label = str(pkg.get("label") or "")
            if label and label in (item_name or ""):
                return True
    except Exception:
        pass
    return False


async def too_many_pending(user_id: int) -> bool:
    """
    Лимит висящих заказов — ОДИН на все входы: и витрина, и чат.

    Раньше проверка жила только в API мини-аппа, и тот же человек спокойно
    набивал заявки через чат. Число держим здесь, чтобы два пути не разъехались.
    """
    from database.db import count_pending_orders

    try:
        return await count_pending_orders(user_id) >= MAX_PENDING_ORDERS_PER_USER
    except Exception:
        return False  # сбой базы не должен закрывать магазин


def _as_int_or_zero(value) -> int:
    """Количество из мини-аппа приходит как есть — строкой, None или мусором."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _shift_date(sql_dt: str, days: int) -> str:
    """'2026-09-19 10:00:00' + 3 дня -> '2026-09-22' (для наглядности в чате)."""
    from datetime import datetime, timedelta

    try:
        base = datetime.strptime(str(sql_dt).replace("T", " ").split(".")[0], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "—"
    return (base + timedelta(days=days)).strftime("%Y-%m-%d")


async def create_order_from_draft(bot: Bot, user_id: int, username: str | None, data: dict) -> dict:
    """
    Создаёт заказ из черновика (то, что лежит в FSM после process_order) и
    выдаёт сумму к оплате. Используется ДВУМЯ путями оформления:
    - из чата, после кнопки «Подтвердить» (handlers/order.py);
    - сразу из мини-аппа (place_order_direct ниже) — там подтверждение уже
      сделано в самой витрине, второй раз спрашивать в чате незачем.
    -> {"order_id": int, "price": int, "pay_amount": int}
    """
    import config
    from database.db import create_order, allocate_and_set_expected_amount

    order_id = await create_order(
        user_id=user_id,
        username=username or "",
        category=data["category"],
        item_name=data["item_name"],
        quantity=data.get("quantity", 1),
        price_uzs=data["price"],
        recipient=data["recipient"],
        recipient_user_id=data.get("recipient_user_id"),
        rent_days=data.get("rent_days"),
        nft_address=data.get("nft_address"),
        base_price_per_day_gram=str(data.get("base_price_per_day_gram", "")) or None,
        nft_preview_url=data.get("nft_preview_url"),
        is_extension=int(data.get("is_extension") or 0),
        parent_order_id=data.get("parent_order_id"),
    )

    # Уникальная сумма (цена + небольшая случайная надбавка) — чтобы по одной
    # только сумме поступления понять, чей это платёж (автопроверка по SMS).
    pay_amount = data["price"]
    if config.UNIQUE_AMOUNT_ENABLED and not wants_exact_price(
        data["category"], data.get("item_name") or ""
    ):
        # Выдача и закрепление суммы — одной транзакцией, иначе два
        # одновременных заказа могут получить одинаковую сумму к оплате.
        pay_amount = await allocate_and_set_expected_amount(
            order_id, data["price"], config.UNIQUE_AMOUNT_MAX_OFFSET
        )

    return {"order_id": order_id, "price": data["price"], "pay_amount": pay_amount}


async def place_order_direct(
    bot: Bot,
    state: FSMContext,
    user_id: int,
    username: str | None,
    full_name: str,
    payload: dict,
) -> dict:
    """
    Оформление заказа ПРЯМО ИЗ ВИТРИНЫ, без шага «Всё верно?» в чате.

    Зачем: человек уже всё выбрал и подтвердил в мини-аппе — просить его
    выйти в чат и нажать там ещё одну кнопку значит оборвать покупку на
    середине. Теперь заказ создаётся сразу, а витрина сама ведёт клиента
    дальше по статусам (оплата -> проверка -> выполнение -> готово).

    В чат при этом всё равно уходит сообщение с номером заказа и реквизитами —
    чтобы у клиента осталась история и возможность прислать чек прямо в чат,
    как раньше.
    """
    import config

    # Тот же самый разбор и проверка данных, что и в обычном пути, просто
    # без сообщения «Всё верно?» — черновик остаётся в state.
    await process_order(bot, state, user_id, username, full_name, payload, announce=False)
    data = await state.get_data()

    created = await create_order_from_draft(bot, user_id, username, data)

    # Состояние как после подтверждения в чате: если клиент по привычке
    # пришлёт чек сообщением в бота, он обработается ровно как раньше.
    await state.update_data(order_id=created["order_id"])
    await state.set_state(OrderStates.waiting_payment_proof)

    lang = await get_user_language(user_id)
    amount_note = ""
    if config.UNIQUE_AMOUNT_ENABLED and created["pay_amount"] != created["price"]:
        # Уникальная сумма + предупреждение про комиссию банка: если она
        # съест часть перевода, на карту придёт меньше и автоподтверждение
        # не сработает. Человек должен узнать об этом ДО оплаты.
        amount_note = (
            f"\n\n⚠️ {t(lang, 'cart_exact_amount')} <b>{format_uzs(created['pay_amount'])}</b>"
            + t(lang, "pay_commission_note")
        )

    from keyboards.user_kb import payment_methods_kb

    try:
        await bot.send_message(
            user_id,
            t(lang, "order_created").format(
                order_id=created["order_id"], price=format_uzs(created["price"])
            )
            + t(lang, "order_pay_card")
            + f"<code>{config.PAYMENT_CARD_NUMBER}</code>\n"
            + f"{t(lang, 'order_pay_receiver')}: {config.PAYMENT_CARD_HOLDER}"
            + amount_note
            + "\n"
            + t(lang, "order_pay_hint_webapp"),
            reply_markup=payment_methods_kb(),
        )
    except Exception:
        pass  # чат не критичен: дальше клиент всё равно ведётся витриной

    return {
        "order_id": created["order_id"],
        "price_uzs": created["price"],
        "pay_amount": created["pay_amount"],
        "item_name": data["item_name"],
        "recipient": data["recipient"],
        "category": data["category"],
    }


async def process_order(
    bot: Bot,
    state: FSMContext,
    user_id: int,
    username: str | None,
    full_name: str,
    payload: dict,
    announce: bool = True,
) -> None:
    """Валидирует payload из мини-аппа и сохраняет черновик заказа в FSM.

    announce=True (по умолчанию) — дополнительно отправляет в чат сообщение
    «Проверьте заказ… Всё верно?» с кнопками (старый путь через чат).
    announce=False — только черновик, без сообщений: так им пользуется
    place_order_direct(), где подтверждение уже сделано в самой витрине.
    """
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
        # Для ПРОДЛЕНИЯ получатель не нужен: подарок уже подключён к профилю
        # клиента, никому ничего доставлять не надо — поэтому отсутствие
        # публичного @username не должно блокировать продление.
        if category == "nft_rent_extend":
            recipient = f"id{user_id}"
            recipient_user_id = user_id
        else:
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
        if category in ("stars", "stars_custom"):
            # Fragment принимает 50..1 000 000 звёзд за заказ. Проверяем здесь,
            # а не только в витрине: количество из мини-аппа приходит обычным
            # полем запроса и его можно подменить. Пропущенный заказ дошёл бы
            # до оплаты и упал на выполнении, зависнув у клиента активным.
            stars_qty = _as_int_or_zero(data.get("quantity"))
            if not (STARS_MIN <= stars_qty <= STARS_MAX):
                lang = await get_user_language(user_id)
                text = t(lang, "stars_limit_error").format(
                    min_stars=f"{STARS_MIN:,}".replace(",", " "),
                    max_stars=f"{STARS_MAX:,}".replace(",", " "),
                )
                await bot.send_message(user_id, text)
                raise OrderError(text)

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

        if not announce:
            return

        lang = await get_user_language(user_id)
        note_line = f"\n{t(lang, 'order_check_note')}: {note}" if note else ""
        await bot.send_message(
            user_id,
            f"{t(lang, 'order_check_title')}\n\n"
            f"{t(lang, 'order_check_item')}: <b>{data['item_name']}</b>\n"
            f"{t(lang, 'order_check_recipient')}: {recipient}{note_line}\n"
            f"{t(lang, 'order_check_total')}: <b>{format_uzs(data['price'])}</b>\n\n"
            f"{t(lang, 'order_check_confirm')}",
            reply_markup=confirm_order_kb(),
        )

    elif category == "nft_rent_extend":
        # ПРОДЛЕНИЕ уже действующей аренды. Цену за день берём НЕ из данных
        # клиента, а из его же оплаченного заказа в нашей базе — так продлить
        # можно только реально свою аренду и только по реальной цене.
        from services.marketapp_service import calc_rent_price
        from services.rent_extension import find_rental

        rental = await find_rental(user_id, (payload.get("nft_address") or "").strip())
        if not rental or not rental["can_extend"]:
            lang = await get_user_language(user_id)
            text = t(lang, "rent_extend_not_found")
            await bot.send_message(user_id, text)
            raise OrderError("rental_not_found")

        try:
            days = int(payload["days"])
        except (KeyError, ValueError, TypeError):
            raise OrderError("bad_days")
        days = max(rental["min_days"], min(days, rental["max_days"]))

        calc = calc_rent_price(rental["base_price_per_day_gram"], days)
        item_name = f"Продление: {rental['item_name']}"

        await state.update_data(
            category="nft_rent",
            is_extension=1,
            parent_order_id=rental["order_id"],
            item_name=item_name,
            nft_address=rental["nft_address"],
            base_price_per_day_gram=rental["base_price_per_day_gram"],
            rent_days=days,
            price=calc["total_to_pay"],
            quantity=1,
            recipient=recipient,
            recipient_user_id=recipient_user_id,
            note=note,
        )
        await state.set_state(OrderStates.confirming)

        if not announce:
            return

        lang = await get_user_language(user_id)
        await bot.send_message(
            user_id,
            f"{t(lang, 'order_check_title')}\n\n"
            f"{t(lang, 'order_check_item')}: <b>{item_name} — +{days} kun</b>\n"
            f"{t(lang, 'rent_extend_until')}: {rental['ends_at'][:10]} → "
            f"{_shift_date(rental['ends_at'], days)}\n"
            f"{t(lang, 'order_check_fee')}: {format_uzs(calc['fee_total_uzs'])} "
            f"({format_uzs(calc['fee_refundable_uzs'])} — {t(lang, 'order_check_fee_refund')})\n"
            f"{t(lang, 'order_check_total')}: <b>{format_uzs(calc['total_to_pay'])}</b>\n\n"
            f"{t(lang, 'order_check_confirm')}",
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
            # Ссылка на конкретный экземпляр подарка (t.me/nft/...). Витрина её
            # уже знает — она же используется для кнопки «посмотреть подарок».
            # После подключения отдадим её клиенту, чтобы он одним нажатием
            # попал на свой гифт и включил показ в профиле.
            nft_preview_url=(payload.get("preview_url") or "").strip() or None,
            base_price_per_day_gram=base_price_per_day_gram,
            rent_days=days,
            price=calc["total_to_pay"],
            quantity=1,
            recipient=recipient,
            recipient_user_id=recipient_user_id,
            note=note,
        )
        await state.set_state(OrderStates.confirming)

        if not announce:
            return

        lang = await get_user_language(user_id)
        note_line = f"\n{t(lang, 'order_check_note')}: {note}" if note else ""
        await bot.send_message(
            user_id,
            f"{t(lang, 'order_check_title')}\n\n"
            f"{t(lang, 'order_check_item')}: <b>{payload['item_name']} — {days} kun</b>\n"
            f"{t(lang, 'order_check_recipient')}: {recipient}{note_line}\n"
            f"{t(lang, 'order_check_fee')}: {format_uzs(calc['fee_total_uzs'])} "
            f"({format_uzs(calc['fee_refundable_uzs'])} — {t(lang, 'order_check_fee_refund')})\n"
            f"{t(lang, 'order_check_total')}: <b>{format_uzs(calc['total_to_pay'])}</b>\n\n"
            f"{t(lang, 'order_check_confirm')}",
            reply_markup=confirm_order_kb(),
        )

    else:
        text = "Неизвестный тип заказа из мини-аппа."
        await bot.send_message(user_id, text)
        raise OrderError(text)
