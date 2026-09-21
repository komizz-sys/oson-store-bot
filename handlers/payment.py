import asyncio

from aiogram import Router, F, Bot
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import config
from database.db import (
    attach_payment_proof, get_order, set_order_status,
    attach_cart_payment_proof, get_cart_orders, set_cart_status,
    find_order_by_receipt, set_receipt_fingerprint, set_cart_receipt_fingerprint,
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


DUPLICATE_RECEIPT = {
    "uz": (
        "⚠️ Bu chek allaqachon boshqa buyurtma uchun yuborilgan.\n\n"
        "Har bir buyurtma alohida to'lanadi. Yangi to'lov qiling va "
        "ayni shu to'lovning chekini yuboring."
    ),
    "ru": (
        "⚠️ Этот чек уже присылали по другому заказу.\n\n"
        "Каждый заказ оплачивается отдельно. Сделайте новый перевод и "
        "пришлите чек именно этого платежа."
    ),
    "en": (
        "⚠️ This receipt was already submitted for another order.\n\n"
        "Each order is paid separately. Make a new transfer and send "
        "the receipt for that payment."
    ),
}


def _is_repeat_receipt(order: dict | None) -> bool:
    """
    Это уже ВТОРОЙ чек по тому же заказу?

    Клиенты часто шлют два скриншота одного платежа: экран «перевод выполнен»
    и следом PDF-квитанцию из банка. Файлы разные, поэтому защита от повторного
    чека их не ловит — и админ получал две одинаковые карточки с двумя парами
    кнопок по одному заказу. Легко нажать «подтвердить» дважды и запутаться.
    """
    if not order:
        return False
    return bool(order.get("payment_proof_file_id")) and order.get("status") == "payment_review"


# Живые задачи-напоминалки: см. комментарий у create_task ниже.
_REMINDER_TASKS: set = set()


def _expected_line(order: dict | None) -> str:
    """
    Строка «ждём ровно N сум» в карточке чека для админа.

    Это главная защита от повторного чека: у каждого заказа своя сумма
    с точностью до сума, и если на скриншоте другая цифра — платёж не по
    этому заказу, каким бы правдоподобным чек ни выглядел.
    """
    if not order:
        return ""
    expected = order.get("expected_amount_uzs")
    if not expected:
        return ""
    return f"\n\n💳 <b>Ждём ровно: {format_uzs(expected)}</b> — сверь с суммой на чеке"


async def _reject_duplicate_receipt(bot: Bot, message: Message, lang, duplicate: dict,
                                    target, sender: str) -> None:
    """
    Чек уже использовали. Клиенту — отказ, админу — короткое уведомление.

    Заказ НЕ переводим в проверку: иначе он попадёт в общий поток чеков, и
    админ будет разбирать одно и то же по десять раз — ровно то, от чего
    защищаемся. Заказ остаётся ждать настоящей оплаты.
    """
    await message.answer(DUPLICATE_RECEIPT.get(lang if lang in DUPLICATE_RECEIPT else "uz"))

    who_before = duplicate.get("username") and f"@{duplicate['username']}" or f"id {duplicate['user_id']}"
    status_ru = {
        "awaiting_payment": "ждёт оплаты", "payment_review": "на проверке",
        "paid": "оплачен", "fulfilling": "выполняется",
        "completed": "выполнен", "rejected": "отменён",
    }.get(duplicate["status"], duplicate["status"])

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔁 <b>Повторный чек — заблокирован</b>\n\n"
                f"{sender} прислал чек, который уже использовали.\n\n"
                f"Сейчас прикладывал к: <b>{target}</b>\n"
                f"Тот же чек был по заказу <b>#{duplicate['id']}</b> "
                f"({duplicate['item_name']}, {who_before}) — {status_ru}.\n\n"
                "Клиенту сказано оплатить заказ отдельно. Тебе делать ничего не нужно.",
            )
        except Exception:
            pass


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
    # Отпечаток файла: при пересылке file_id меняется, а file_unique_id — нет.
    # Именно по нему ловим один и тот же чек, приложенный к разным заказам.
    fingerprint = (
        message.photo[-1].file_unique_id if message.photo else message.document.file_unique_id
    )
    lang = await get_user_language(message.from_user.id)
    sender = f"@{message.from_user.username or message.from_user.id} (id: {message.from_user.id})"

    duplicate = await find_order_by_receipt(
        fingerprint, exclude_order_id=order_id, exclude_cart_id=cart_id
    )
    if duplicate:
        await _reject_duplicate_receipt(
            bot, message, lang, duplicate, order_id or cart_id, sender
        )
        await state.clear()
        return

    if cart_id:
        # Один чек на всю корзину: помечаем все её товары и отправляем админу
        # ОДНО сообщение с общей суммой и одной парой кнопок.
        cart_before = await get_cart_orders(cart_id)
        repeat = _is_repeat_receipt(cart_before[0] if cart_before else None)
        await attach_cart_payment_proof(cart_id, file_id)
        await set_cart_receipt_fingerprint(cart_id, fingerprint)
        cart_orders = await get_cart_orders(cart_id)
        total = sum(o["price_uzs"] for o in cart_orders)
        items = "\n".join(f"  • {o['item_name']} → {o['recipient']}" for o in cart_orders)
        caption = (
            f"🛒 <b>Новый чек по корзине {cart_id}</b> ({len(cart_orders)} тов.)\n"
            f"От: {sender}\n"
            f"{items}\n"
            f"Итого: {format_uzs(total)}"
            + _expected_line(cart_orders[0] if cart_orders else None)
        )
        cart_order_ids = [o["id"] for o in cart_orders]
        markup = None if repeat else admin_review_cart_kb(cart_id)
        if repeat:
            caption = f"🔁 <b>Ещё один чек по корзине {cart_id}</b>\n" + caption.split("\n", 1)[1]
            caption += "\n\n☝️ Кнопки — в первом сообщении по этой корзине."
        remind_id = None if repeat else (cart_orders[0]["id"] if cart_orders else None)
    else:
        cart_order_ids = []
        repeat = _is_repeat_receipt(await get_order(order_id))
        await attach_payment_proof(order_id, file_id)
        await set_receipt_fingerprint(order_id, fingerprint)
        order = await get_order(order_id)
        caption = (
            f"🆕 <b>Новый чек по заказу #{order_id}</b>\n"
            f"От: {sender}\n"
            f"Товар: {order['item_name'] if order else '—'}\n"
            f"Получатель: {order['recipient'] if order else '—'}\n"
            f"Сумма: {format_uzs(order['price_uzs']) if order else '—'}"
            + _expected_line(order)
        )
        markup = None if repeat else admin_review_kb(order_id)
        if repeat:
            caption = (
                f"🔁 <b>Ещё один чек по заказу #{order_id}</b>\n"
                + caption.split("\n", 1)[1]
                + "\n\n☝️ Кнопки — в первом сообщении по этому заказу."
            )
        # Напоминалку на повторный чек не ставим: по этому заказу она уже идёт.
        remind_id = None if repeat else order_id

    await message.answer(t(lang, "proof_received"))
    await state.clear()

    from database.db import remember_admin_card

    card_ids = cart_order_ids if cart_id else [order_id]
    for admin_id in config.ADMIN_IDS:
        try:
            if message.photo:
                sent = await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=markup)
            else:
                sent = await bot.send_document(admin_id, file_id, caption=caption, reply_markup=markup)
            # Запоминаем сообщение, чтобы потом дописать в него «ВЫПОЛНЕНО»
            # и результат автооплаты — админу не придётся искать это в ленте.
            if not repeat:
                try:
                    await remember_admin_card(card_ids, admin_id, sent.message_id, caption)
                except Exception:
                    pass
        except Exception:
            pass

    if remind_id:
        # Ссылку на задачу держим сами: asyncio хранит на свои задачи только
        # слабую ссылку, и без этого напоминание может быть собрано сборщиком
        # мусора посреди ожидания — админ просто не получит пинок по чеку.
        task = asyncio.create_task(_remind_admin_if_still_pending(bot, remind_id, cart_id))
        _REMINDER_TASKS.add(task)
        task.add_done_callback(_REMINDER_TASKS.discard)


@router.message(OrderStates.waiting_payment_proof, F.text == "/start")
async def handle_start_in_state(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню обновлено. Введите /start ещё раз.")


@router.message(OrderStates.waiting_payment_proof)
async def wrong_proof_format(message: Message):
    # Команды пропускаем дальше по цепочке. Иначе человек, ждущий оплаты,
    # оказывался в ловушке: на /balans, /operator и любую другую команду бот
    # отвечал «пришлите чек» — и выйти из этого состояния было нечем.
    if (message.text or "").startswith("/"):
        raise SkipHandler()
    await message.answer("Пришлите, пожалуйста, скриншот или файл чека об оплате 📎 (или нажмите «Отмена» выше)")


@router.message(F.photo | F.document)
async def orphan_receipt(message: Message, state: FSMContext, bot: Bot):
    """
    Чек прислали в чат, а состояния нет — находим заказ сами.

    Когда это случается: бот перезапустился (состояние живёт в памяти и при
    рестарте теряется), или клиент оформил заказ в витрине неделю назад и
    только сейчас прислал чек в переписку. Раньше бот отвечал «не нашёл
    номер заказа» — человек оплатил и упёрся в тупик.

    Ищем у него незакрытый заказ и обрабатываем чек как обычно. Если такого
    заказа нет, пропускаем сообщение дальше: это просто фотография, а не чек.
    """
    from database.db import get_user_orders

    try:
        orders = await get_user_orders(message.from_user.id)
    except Exception:
        raise SkipHandler()

    active = next(
        (o for o in orders if o["status"] in ("awaiting_payment", "payment_review")),
        None,
    )
    if not active:
        raise SkipHandler()  # не чек — не наше дело

    await state.update_data(order_id=active["id"], cart_id=active.get("cart_id"))
    await state.set_state(OrderStates.waiting_payment_proof)
    await got_payment_proof(message, state, bot)
