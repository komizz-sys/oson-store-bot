import re
from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import config
from database.db import upsert_user, get_user_orders, get_user_language, set_user_language, set_user_source
from keyboards.user_kb import main_menu_kb, language_select_kb, subscribe_gate_kb
from services.prices import format_uzs
from services.i18n import t
from services.subscription import is_subscribed
from handlers.states import OrderStates

router = Router()

STATUS_KEYS = {
    "awaiting_payment": "status_awaiting_payment",
    "payment_review": "status_payment_review",
    "paid": "status_paid",
    "fulfilling": "status_fulfilling",
    "completed": "status_completed",
    "rejected": "status_rejected",
}


def _strip_custom_emoji(text: str) -> str:
    """Убирает теги анимированных эмодзи, оставляя обычный эмодзи внутри.
    Нужно как запасной вариант: Telegram принимает <tg-emoji> только если у
    ВЛАДЕЛЬЦА бота есть Premium. Если подписки нет (или она кончилась),
    сообщение целиком отклоняется — и без этого отката /start просто
    перестал бы работать."""
    return re.sub(r"<tg-emoji emoji-id='\d+'>(.*?)</tg-emoji>", r"\1", text)


async def _answer_welcome(target, text: str, markup):
    """Пробуем с анимированными эмодзи, при отказе — тем же текстом без них."""
    try:
        await target.answer(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        await target.answer(_strip_custom_emoji(text), reply_markup=markup, disable_web_page_preview=True)


def _welcome_text(lang: str, user) -> str:
    """Приветствие с обращением по имени. Имя оборачиваем в ссылку на
    профиль — так Telegram подсвечивает его, как у крупных магазинов."""
    name = (getattr(user, "first_name", None) or "").strip() or "do'stim"
    safe = name.replace("<", "").replace(">", "").replace("&", "")
    mention = f'<a href="tg://user?id={user.id}">{safe}</a>'
    return t(lang, "welcome").format(name=mention)


async def drop_reply_kb(message) -> None:
    """
    Снять с телефона старую кнопку магазина на клавиатуре чата.

    Просто перестать её присылать мало: у тех, кто уже пользовался ботом,
    она останется висеть навсегда и будет открывать витрину по старому пути.
    Убрать её можно только сообщением с ReplyKeyboardRemove — поэтому шлём
    техническое сообщение и сразу удаляем, чтобы не мусорить в чате.
    """
    from aiogram.types import ReplyKeyboardRemove

    try:
        tmp = await message.answer("⌨️", reply_markup=ReplyKeyboardRemove())
        await tmp.delete()
    except Exception:
        pass  # не смогли — не страшно, меню выше всё равно открывает магазин


async def _show_main_menu(message_or_call_message, user_id: int, user=None):
    lang = await get_user_language(user_id)
    if not lang:
        await message_or_call_message.answer(
            "🌐 Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=language_select_kb(),
        )
        return
    text = _welcome_text(lang, user) if user else t(lang, "welcome").format(name="do'stim")
    await _answer_welcome(message_or_call_message, text, main_menu_kb(lang))
    await drop_reply_kb(message_or_call_message)


_SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _clean_source(args: str | None) -> str | None:
    """Метка из t.me/bot?start=reel1 → "reel1". Мусор — None."""
    value = (args or "").strip()[:32]
    return value if value and _SOURCE_RE.match(value) else None


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    await upsert_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name)

    # Рекламная метка — СРАЗУ, до проверки подписки: если человек не подписан,
    # он уйдёт на экран подписки, а после кнопки «Проверить» метки в
    # сообщении уже нет — она потерялась бы.
    source = _clean_source(command.args if command else None)
    if source:
        try:
            await set_user_source(message.from_user.id, source)
        except Exception:
            pass  # статистика не должна ломать /start

    # По желанию владельца (AD_SKIP_SUBSCRIPTION=1) пришедших из рекламы не
    # заставляем подписываться на канал перед покупкой.
    skip_sub = bool(
        config.AD_SKIP_SUBSCRIPTION and source
        and source.lower().startswith(("reel", "ad"))
    )
    if skip_sub:
        await _show_main_menu(message, message.from_user.id, message.from_user)
        return

    if not await is_subscribed(message.bot, message.from_user.id):
        lang = await get_user_language(message.from_user.id)
        await message.answer(t(lang, "sub_required_text"), reply_markup=subscribe_gate_kb(lang))
        return

    await _show_main_menu(message, message.from_user.id, message.from_user)


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    """Показывает числовой Telegram ID — удобно, чтобы сверить с ADMIN_IDS на Railway."""
    await message.answer(f"🆔 Твой Telegram ID: <code>{message.from_user.id}</code>")


@router.message(Command("ping"))
async def cmd_ping(message: Message):
    """Диагностическая команда — если бот не отвечает на неё, значит на Railway
    запущена не та версия кода, которая сейчас в GitHub/зип-архиве."""
    await message.answer("pong ✅ (deploy check v1)")


@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    if not await is_subscribed(call.bot, call.from_user.id):
        lang = await get_user_language(call.from_user.id)
        await call.answer(t(lang, "sub_still_not"), show_alert=True)
        return

    await call.answer("✅")
    await _show_main_menu(call.message, call.from_user.id, call.from_user)


@router.callback_query(F.data.startswith("setlang:"))
async def set_language(call: CallbackQuery):
    lang = call.data.split(":")[1]
    await set_user_language(call.from_user.id, lang)

    await call.message.edit_text(t(lang, "language_changed"))
    await _answer_welcome(call.message, _welcome_text(lang, call.from_user), main_menu_kb(lang))
    await drop_reply_kb(call.message)
    await call.answer()


@router.callback_query(F.data == "menu:change_language")
async def change_language(call: CallbackQuery):
    await call.message.edit_text(
        "🌐 Tilni tanlang / Выберите язык / Choose language:",
        reply_markup=language_select_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "menu:back")
async def back_to_menu(call: CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    text = _welcome_text(lang, call.from_user)
    try:
        await call.message.edit_text(text, reply_markup=main_menu_kb(lang), disable_web_page_preview=True)
    except Exception:
        await call.message.edit_text(_strip_custom_emoji(text), reply_markup=main_menu_kb(lang), disable_web_page_preview=True)
    await call.answer()


# Заказы, которые ещё не закрыты: по ним клиенту есть что делать.
ACTIVE_STATUSES = ("awaiting_payment", "payment_review", "paid", "fulfilling")


@router.callback_query(F.data == "menu:my_orders")
async def my_orders(call: CallbackQuery, state: FSMContext):
    """
    Мои заказы.

    Раньше здесь был просто список строк «#97 — Premium — 49 000 — ждёт оплаты».
    Для истории этого хватает, а для НЕЗАКРЫТОГО заказа — нет: реквизиты и
    точная сумма показывались только в витрине, и человек, закрывший мини-апп,
    оставался без единственных цифр, которые ему нужны. Сам заказ при этом
    никуда не девался — просто его не было видно.

    Теперь незакрытый заказ показывается первым, с картой и точной суммой, и
    чек по нему можно прислать прямо сюда, в чат.
    """
    import config
    from keyboards.user_kb import payment_methods_kb

    lang = await get_user_language(call.from_user.id)
    orders = await get_user_orders(call.from_user.id)

    if not orders:
        await call.message.edit_text(t(lang, "my_orders_empty"), reply_markup=main_menu_kb(lang))
        await call.answer()
        return

    active = next((o for o in orders if o["status"] in ACTIVE_STATUSES), None)
    lines = [t(lang, "my_orders_header")]

    for o in orders:
        status = t(lang, STATUS_KEYS.get(o["status"], "status_awaiting_payment"))
        mark = "▶️ " if active and o["id"] == active["id"] else ""
        lines.append(f"{mark}#{o['id']} — {o['item_name']} — {format_uzs(o['price_uzs'])} — {status}")

    markup = main_menu_kb(lang)

    if active and active["status"] == "awaiting_payment":
        amount = active.get("expected_amount_uzs") or active["price_uzs"]
        lines.append("")
        lines.append(t(lang, "my_orders_active_title").format(order_id=active["id"]))
        lines.append(t(lang, "order_pay_card") + f"<code>{config.PAYMENT_CARD_NUMBER}</code>")
        lines.append(f"{t(lang, 'order_pay_receiver')}: {config.PAYMENT_CARD_HOLDER}")
        lines.append("")
        lines.append(t(lang, "my_orders_exact").format(amount=format_uzs(amount)))
        lines.append(t(lang, "my_orders_send_here"))

        # Ставим то же состояние, что и после оформления: чек, присланный
        # сюда сообщением, прикрепится именно к этому заказу. Без этого после
        # перезапуска бота состояние терялось и чек уходил в пустоту.
        await state.update_data(
            order_id=active["id"],
            cart_id=active.get("cart_id"),
        )
        await state.set_state(OrderStates.waiting_payment_proof)
        markup = payment_methods_kb()

    await call.message.edit_text("\n".join(lines), reply_markup=markup)
    await call.answer()


@router.message(Command("balans", "balance"))
async def balance_cmd(message: Message):
    """
    Баланс клиента: остаток и последние операции.

    Баланс нужен потому, что банк удерживает комиссию и «ровно столько-то»
    на карту почти никогда не приходит. На счёт зачисляется сколько дошло,
    а заказы с него оплачиваются точно и мгновенно.
    """
    from database.db import get_balance, get_balance_history

    lang = await get_user_language(message.from_user.id)
    balance = await get_balance(message.from_user.id)
    lines = [t(lang, "balance_title").format(balance=format_uzs(balance)), ""]

    history = await get_balance_history(message.from_user.id, limit=10)
    if not history:
        lines.append(t(lang, "balance_empty"))
    else:
        for h in history:
            sign = "➕" if h["delta_uzs"] > 0 else "➖"
            lines.append(f"{sign} {format_uzs(abs(h['delta_uzs']))} — {h['reason'] or ''}")

    lines.append("")
    lines.append(t(lang, "balance_topup_hint"))
    await message.answer("\n".join(lines), reply_markup=main_menu_kb(lang))
