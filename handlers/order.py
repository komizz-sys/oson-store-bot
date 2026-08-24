from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import create_order
from handlers.states import OrderStates
from keyboards.user_kb import stars_kb, premium_kb, confirm_order_kb, payment_methods_kb
from services.prices import get_stars_packages, get_premium_packages, format_uzs
from services.marketapp_service import get_available_gifts, calc_rent_price
from services.telegram_gifts import get_catalog as get_simple_gift_catalog
from services.i18n import t
from database.db import get_user_language

router = Router()


# ---------- Навигация по разделам ----------

@router.callback_query(F.data == "menu:stars")
async def show_stars(call: CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    await call.message.edit_text(t(lang, "stars_header"), reply_markup=stars_kb())
    await call.answer()


@router.callback_query(F.data == "menu:premium")
async def show_premium(call: CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    await call.message.edit_text(t(lang, "premium_header"), reply_markup=premium_kb())
    await call.answer()


@router.callback_query(F.data == "menu:nft_rent")
async def show_nft_rent(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("🔄 Загружаю актуальный список гифтов...")

    gifts = await get_available_gifts(limit=10)
    if not gifts:
        await call.message.edit_text(
            "😕 Не удалось получить список гифтов с MarketApp прямо сейчас. "
            "Попробуйте чуть позже.",
        )
        return

    await state.update_data(rent_gifts_cache={g["nft_address"]: g for g in gifts})

    b = InlineKeyboardBuilder()
    for g in gifts:
        b.button(
            text=f"🖼 {g['name']} — от {format_uzs(g['price_per_day_uzs_with_markup'])}/день",
            callback_data=f"buy:nft_rent:{g['nft_address']}",
        )
    b.button(text="⬅️ Назад", callback_data="menu:back")
    b.adjust(1)

    await call.message.edit_text(
        "🖼 Доступные для аренды гифты (цены уже с наценкой, за 1 день):",
        reply_markup=b.as_markup(),
    )


# ---------- Выбор Stars / Premium ----------

@router.callback_query(F.data.startswith("buy:stars:"))
async def choose_stars(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":")[2])
    pkg = get_stars_packages()[idx]
    item_name = f"{pkg['amount']} звёзд"
    price = pkg["price_uzs"]

    await state.update_data(category="stars", item_name=item_name, price=price, quantity=pkg["amount"])
    await state.set_state(OrderStates.entering_recipient)
    await call.message.edit_text(
        f"Вы выбрали: <b>{item_name}</b> — {format_uzs(price)}\n\n"
        "Введите @username аккаунта, куда отправить звёзды:"
    )
    await call.answer()


@router.callback_query(F.data.startswith("buy:premium:"))
async def choose_premium(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":")[2])
    pkg = get_premium_packages()[idx]
    item_name = f"Premium — {pkg['label']}"
    price = pkg["price_uzs"]

    await state.update_data(category="premium", item_name=item_name, price=price, quantity=1)
    await state.set_state(OrderStates.entering_recipient)
    await call.message.edit_text(
        f"Вы выбрали: <b>{item_name}</b> — {format_uzs(price)}\n\n"
        "Введите @username аккаунта, на который оформить Premium:"
    )
    await call.answer()


@router.callback_query(F.data == "menu:simple_gift")
async def show_simple_gift(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("🔄 Загружаю каталог подарков...")

    try:
        gifts = await get_simple_gift_catalog(call.bot)
    except Exception:
        gifts = []

    if not gifts:
        await call.message.edit_text("😕 Не удалось получить каталог подарков сейчас. Попробуйте позже.")
        return

    await state.update_data(simple_gifts_cache={g["id"]: g for g in gifts})

    b = InlineKeyboardBuilder()
    for g in gifts[:15]:
        b.button(
            text=f"{g['sticker_emoji']} {g['star_count']}⭐ — {format_uzs(g['price_uzs'])}",
            callback_data=f"buy:simple_gift:{g['id']}",
        )
    b.button(text="⬅️ Назад", callback_data="menu:back")
    b.adjust(1)

    await call.message.edit_text("🎁 Выберите подарок:", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("buy:simple_gift:"))
async def choose_simple_gift(call: CallbackQuery, state: FSMContext):
    gift_id = call.data.split(":", 2)[2]
    data = await state.get_data()
    gift = (data.get("simple_gifts_cache") or {}).get(gift_id)

    if not gift:
        await call.answer("Список устарел, откройте раздел заново", show_alert=True)
        return

    item_name = f"Подарок {gift['sticker_emoji']} ({gift['star_count']}⭐)"
    await state.update_data(
        category="simple_gift", item_name=item_name, price=gift["price_uzs"],
        quantity=1, nft_address=gift["id"],  # переиспользуем поле под gift_id
    )
    await state.set_state(OrderStates.entering_recipient)
    await call.message.edit_text(
        f"Вы выбрали: <b>{item_name}</b> — {format_uzs(gift['price_uzs'])}\n\n"
        "⚠️ Получатель должен хотя бы раз написать этому боту (/start), "
        "иначе Telegram не даст боту его определить.\n\n"
        "Введите @username получателя:"
    )
    await call.answer()


# ---------- Выбор гифта для аренды ----------

@router.callback_query(F.data.startswith("buy:nft_rent:"))
async def choose_nft_rent(call: CallbackQuery, state: FSMContext):
    nft_address = call.data.split(":", 2)[2]
    data = await state.get_data()
    gift = (data.get("rent_gifts_cache") or {}).get(nft_address)

    if not gift:
        await call.answer("Список устарел, откройте раздел заново", show_alert=True)
        return

    await state.update_data(
        category="nft_rent",
        item_name=gift["name"],
        nft_address=gift["nft_address"],
        base_price_per_day_gram=gift["base_price_per_day_gram"],
        min_days=gift["min_duration_days"],
        max_days=gift["max_duration_days"],
    )
    await state.set_state(OrderStates.entering_rent_days)
    await call.message.edit_text(
        f"Вы выбрали аренду: <b>{gift['name']}</b>\n"
        f"Доступный срок: от {gift['min_duration_days']} до {gift['max_duration_days']} дней\n\n"
        "На сколько дней хотите арендовать? Введите число:"
    )
    await call.answer()


@router.message(OrderStates.entering_rent_days)
async def got_rent_days(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("Введите число дней, например: 3")
        return

    days = int(message.text.strip())
    data = await state.get_data()

    if not (data["min_days"] <= days <= data["max_days"]):
        await message.answer(
            f"Для этого гифта срок аренды должен быть от {data['min_days']} "
            f"до {data['max_days']} дней. Введите другое число:"
        )
        return

    calc = calc_rent_price(data["base_price_per_day_gram"], days)
    await state.update_data(rent_days=days, price=calc["total_to_pay"], quantity=1)
    await state.set_state(OrderStates.entering_recipient)
    await message.answer(
        f"Аренда на {days} дн.:\n"
        f"Стоимость (+20%): {format_uzs(calc['with_markup'])}\n"
        f"Комиссия сети: {format_uzs(calc['fee_total_uzs'])} "
        f"(вернётся вам после аренды: {format_uzs(calc['fee_refundable_uzs'])})\n"
        f"<b>Итого к оплате: {format_uzs(calc['total_to_pay'])}</b>\n\n"
        "Введите @username, на который оформить получение подарка:"
    )


# ---------- Получатель ----------

@router.message(OrderStates.entering_recipient)
async def got_recipient(message: Message, state: FSMContext):
    recipient = message.text.strip()
    if not recipient.startswith("@"):
        await message.answer("Введите @username, например: @ivanov")
        return

    data = await state.update_data(recipient=recipient)
    await state.set_state(OrderStates.confirming)
    await message.answer(
        f"Проверьте заказ:\n\n"
        f"Товар: <b>{data['item_name']}</b>\n"
        f"Получатель: {recipient}\n"
        f"Сумма к оплате: <b>{format_uzs(data['price'])}</b>\n\n"
        "Всё верно?",
        reply_markup=confirm_order_kb(),
    )


# ---------- Подтверждение / отмена ----------

@router.callback_query(F.data == "order:cancel", OrderStates.confirming)
async def cancel_order(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Заказ отменён. Наберите /start чтобы вернуться в меню.")
    await call.answer()


@router.callback_query(F.data == "order:confirm", OrderStates.confirming)
async def confirm_order(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    order_id = await create_order(
        user_id=call.from_user.id,
        username=call.from_user.username or "",
        category=data["category"],
        item_name=data["item_name"],
        quantity=data.get("quantity", 1),
        price_uzs=data["price"],
        recipient=data["recipient"],
        rent_days=data.get("rent_days"),
        nft_address=data.get("nft_address"),
        base_price_per_day_gram=str(data.get("base_price_per_day_gram", "")) or None,
    )
    await state.update_data(order_id=order_id)
    await state.set_state(OrderStates.waiting_payment_proof)

    import config
    await call.message.edit_text(
        f"✅ Заказ #{order_id} создан на сумму <b>{format_uzs(data['price'])}</b>.\n\n"
        f"Переведите сумму на карту:\n"
        f"<code>{config.PAYMENT_CARD_NUMBER}</code>\n"
        f"Получатель: {config.PAYMENT_CARD_HOLDER}\n\n"
        "После оплаты пришлите сюда скриншот/чек — заказ уйдёт на проверку админу.",
        reply_markup=payment_methods_kb(),
    )
    await call.answer()
