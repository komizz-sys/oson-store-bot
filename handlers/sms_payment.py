"""
Автопроверка оплаты: SMS-пересыльщик на телефоне отправляет текст входящих
SMS от банка в отдельный Telegram-чат (группу/канал), куда добавлен этот бот.
Бот вытаскивает из текста сумму поступления и ищет заказ с точно такой же
expected_amount_uzs (см. database/db.py: allocate_unique_amount) — если нашёл,
подтверждает оплату автоматически, без скриншота и без нажатия кнопки админом.

⚠️ ВАЖНО — регулярка суммы ещё не подогнана под конкретный банк:
Формат SMS у каждого банка/агрегатора свой (Uzcard, Humo, Kapitalbank и т.д.
пишут по-разному: где-то "Popolnenie", где-то "Зачисление", по-разному стоят
пробелы/точки в сумме). Регулярка ниже — общая заготовка (ищет число вида
1 234 567 или 1.234.567 перед словом "сум"/"so'm"/"uzs" в тексте).

ЧТО ИСПРАВЛЕНО (сентябрь 2026): раньше бот разбирал ЛЮБУЮ SMS с суммой —
в том числе твои собственные покупки в обычных магазинах ("Oplata 45 000 sum,
KORZINKA") — и на каждую такую SMS писал админу "сумма не совпала ни с одним
заказом". Теперь:
  1) SMS о СПИСАНИИ (покупка/оплата/перевод/минус перед суммой) игнорируются
     полностью — они физически не могут быть оплатой заказа;
  2) по умолчанию рассматриваются только SMS о ПОСТУПЛЕНИИ
     (config.SMS_INCOME_ONLY);
  3) сообщение "не совпала ни с одним заказом" по умолчанию ВЫКЛЮЧЕНО
     (config.SMS_UNMATCHED_ALERTS) — включай только на время настройки.

Полностью отключить автоподтверждение по SMS можно без правки кода:
UNIQUE_AMOUNT_ENABLED=false в переменных Railway.
"""

import re

from aiogram import Router, F, Bot
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
from database.db import (
    get_order_by_expected_amount, get_cart_orders, find_orders_by_base_price,
    find_expired_order_by_amount, get_order, set_order_status, set_cart_status,
    find_underpaid_orders, get_user_language,
    remember_topup, find_topup_order, clear_topup,
    find_topup_requests, close_topup_request, credit_balance,
)
from handlers.admin import finalize_payment, finalize_cart_payment
from services.i18n import t

router = Router()


async def _credit_topup(bot: Bot, amount: int, topup: dict) -> None:
    """Зачислить пополнение и сказать об этом клиенту и админу."""
    from services.prices import format_uzs

    user_id = topup["user_id"]

    # СНАЧАЛА закрываем заявку, и только если она закрылась именно нами —
    # зачисляем. Обратный порядок дарил деньги: дубль SMS или два админа,
    # нажавшие кнопку каждый в своём чате, давали два зачисления за один
    # перевод.
    try:
        if not await close_topup_request(topup["id"], amount):
            print(f"[BALANCE] заявка {topup['id']} уже закрыта — повторно не зачисляю", flush=True)
            return
    except Exception as e:
        print(f"[BALANCE] не удалось закрыть заявку {topup['id']}: {e}", flush=True)
        return

    try:
        balance = await credit_balance(user_id, amount, "Пополнение баланса")
    except Exception as e:
        print(f"[BALANCE] не удалось зачислить {amount} клиенту {user_id}: {e}", flush=True)
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ Пришло {format_uzs(amount)} — это пополнение клиента "
                    f"<code>{user_id}</code>, но зачислить не вышло: {e}\n"
                    f"Зачисли вручную: <code>/balance {user_id} +{amount}</code>",
                )
            except Exception:
                pass
        return

    lang = await get_user_language(user_id) or "uz"
    if lang not in ("uz", "ru", "en"):
        lang = "uz"

    # Если пришло заметно меньше ожидаемого — говорим об этом прямо, но
    # спокойно: деньги на счету, просто банк взял своё. Просить доплату
    # здесь НЕ нужно, в этом и весь смысл баланса.
    short = max(0, int(topup["expected_uzs"]) - amount)
    try:
        text = t(lang, "topup_done").format(
            amount=format_uzs(amount), balance=format_uzs(balance)
        )
        if short > 0:
            text += "\n\n" + t(lang, "topup_fee_note").format(fee=format_uzs(short))
        await bot.send_message(user_id, text)
    except Exception:
        pass

    print(f"[BALANCE] +{amount} клиенту {user_id}, остаток {balance}", flush=True)
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💼 Баланс пополнен: <b>{format_uzs(amount)}</b>\n"
                f"Клиент: <code>{user_id}</code> · остаток {format_uzs(balance)}"
                + (f"\nБанк удержал {format_uzs(short)}" if short else ""),
            )
        except Exception:
            pass


async def _ask_admin_which_match(bot: Bot, amount: int,
                                 orders: list[dict], topups: list[dict]) -> None:
    """
    Под сумму подошло больше одного варианта — решает человек.

    Автоматика тут запрещена: ошибиться значит либо подарить деньги одного
    клиента другому, либо выполнить чужой заказ. Показываем всех кандидатов
    и даём по кнопке на каждого.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from services.prices import format_uzs

    b = InlineKeyboardBuilder()
    lines = [
        f"❓ <b>Пришло {format_uzs(amount)} — подходит несколько вариантов.</b>\n",
        "Автоматически не подтверждаю: ошибка тут стоит денег. Выбери сам:",
    ]

    for o in orders:
        who = o.get("username") and f"@{o['username']}" or f"id {o['user_id']}"
        expected = o.get("expected_amount_uzs") or o["price_uzs"]
        lines.append(
            f"  🛒 заказ <b>#{o['id']}</b> — {o['item_name']} · от {who} · ждём {format_uzs(expected)}"
        )
        if o.get("cart_id"):
            b.button(text=f"✅ Заказ {o['id']} (корзина)", callback_data=f"admin:approve_cart:{o['cart_id']}")
        else:
            b.button(text=f"✅ Заказ #{o['id']}", callback_data=f"admin:approve:{o['id']}")

    for tp in topups:
        lines.append(
            f"  💼 пополнение клиента <code>{tp['user_id']}</code> · ждём {format_uzs(tp['expected_uzs'])}"
        )
        b.button(
            text=f"💼 Пополнение клиенту {tp['user_id']}",
            callback_data=f"topup:credit:{tp['id']}:{amount}",
        )

    b.button(text="🚫 Не наш платёж", callback_data="admin:sms_ignore")
    b.adjust(1)

    print(f"[SMS] {amount}: заказов {len(orders)}, пополнений {len(topups)}", flush=True)
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "\n".join(lines), reply_markup=b.as_markup())
        except Exception:
            pass


class TopupAmountStates(StatesGroup):
    waiting_amount = State()


@router.callback_query(F.data.startswith("topup:manual:"))
async def topup_ask_amount(call: CallbackQuery, state: FSMContext):
    """Админ вводит сумму с чека руками — банк удержал комиссию и дошло меньше."""
    if call.from_user.id not in config.ADMIN_IDS:
        await call.answer("Только для админа", show_alert=True)
        return

    topup_id = int(call.data.split(":")[2])
    from database.db import get_pending_topup_by_id

    topup = await get_pending_topup_by_id(topup_id)
    if not topup:
        await call.answer("Эта заявка уже закрыта", show_alert=True)
        return

    await state.set_state(TopupAmountStates.waiting_amount)
    await state.update_data(topup_id=topup_id)
    await call.message.answer(
        "Сколько реально пришло на карту? Напиши число.\n"
        "Например: <code>4855</code>\n\n"
        "Отменить — /cancel"
    )
    await call.answer()


@router.message(TopupAmountStates.waiting_amount)
async def topup_take_amount(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    text = (message.text or "").strip()
    if text.startswith("/"):
        await state.clear()
        await message.answer("Отменено.")
        return

    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        await message.answer("Нужно число. Например: <code>4855</code>")
        return
    amount = int(digits)
    if amount <= 0 or amount > 100_000_000:
        await message.answer("Сумма выглядит странно. Напиши число ещё раз.")
        return

    data = await state.get_data()
    await state.clear()

    from database.db import get_pending_topup_by_id

    topup = await get_pending_topup_by_id(int(data.get("topup_id") or 0))
    if not topup:
        await message.answer("Эта заявка уже закрыта — ничего не зачислил.")
        return

    await _credit_topup(bot, amount, topup)


@router.callback_query(F.data.startswith("topup:reject:"))
async def topup_reject(call: CallbackQuery, bot: Bot):
    """Чек не тот или деньги не пришли — закрываем заявку без зачисления."""
    if call.from_user.id not in config.ADMIN_IDS:
        await call.answer("Только для админа", show_alert=True)
        return

    topup_id = int(call.data.split(":")[2])
    from database.db import get_pending_topup_by_id, close_topup_request, get_user_language

    topup = await get_pending_topup_by_id(topup_id)
    if not topup:
        await call.answer("Уже закрыта", show_alert=True)
        return

    await close_topup_request(topup_id, 0)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Отклонено")

    lang = await get_user_language(topup["user_id"]) or "uz"
    if lang not in ("uz", "ru", "en"):
        lang = "uz"
    try:
        await bot.send_message(topup["user_id"], t(lang, "topup_rejected"))
    except Exception:
        pass


@router.callback_query(F.data.startswith("topup:credit:"))
async def credit_topup_manually(call: CallbackQuery, bot: Bot):
    """Админ выбрал, чьё это пополнение."""
    if call.from_user.id not in config.ADMIN_IDS:
        await call.answer("Только для админа", show_alert=True)
        return

    _, _, topup_id, amount = call.data.split(":")
    from database.db import get_pending_topup_by_id

    topup = await get_pending_topup_by_id(int(topup_id))
    if not topup:
        await call.answer("Эта заявка уже закрыта", show_alert=True)
        return

    await _credit_topup(bot, int(amount), topup)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Зачислено")


async def _handle_underpayment(bot: Bot, amount: int, candidates: list[dict]) -> None:
    """
    Денег пришло МЕНЬШЕ, чем ждали по заказу.

    Почти всегда это не обман, а привычка округлять: заказу выдана сумма
    11 207, человек отправил 11 000. Деньги на карте, заказ висит, и раньше
    об этом никто не узнавал — ни клиент, ни админ.

    Что делаем:
    - клиенту пишем, сколько именно осталось доплатить (только если кандидат
      ОДИН — иначе непонятно, кому писать);
    - админу показываем карточку с кнопкой «принять как есть»: недостача
      обычно копеечная, и гонять человека за второй перевод на 107 сум —
      верный способ потерять клиента. Решение остаётся за живым человеком.

    Автоматически такой платёж не подтверждаем НИКОГДА: смысл уникальной
    надбавки в том, что она точно указывает на заказ. Неточная сумма этой
    гарантии не даёт.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from services.prices import format_uzs

    print(
        f"[SMS] поступление {amount} меньше ожидаемого, кандидатов: {len(candidates)}",
        flush=True,
    )

    # Кандидатов несколько — кнопок НЕ даём и клиенту НЕ пишем.
    #
    # Подписи у кнопок были бы почти одинаковые, отличался бы только номер, и
    # промах в спешке означает: выполнить чужой заказ, а заплатившего оставить
    # ни с чем. Пусть админ сверит с чеком в истории.
    if len(candidates) > 1:
        lines = [
            f"💰 <b>Пришло {format_uzs(amount)} — меньше, чем ждём.</b>\n",
            f"⚠️ Под эту сумму подходит <b>{len(candidates)} заказа</b> — "
            "по сумме их не различить, поэтому кнопок не даю:",
        ]
        for o in candidates:
            who = o.get("username") and f"@{o['username']}" or f"id {o['user_id']}"
            expected = o.get("expected_amount_uzs") or o["price_uzs"]
            short = max(0, expected - amount)
            lines.append(
                f"  • <b>#{o['id']}</b> — {o['item_name']} · от {who} · "
                f"не хватает {format_uzs(short)}"
            )
        lines.append("\nСверь чек в истории заказов и подтверди нужный кнопкой под чеком клиента.")
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, "\n".join(lines))
            except Exception:
                pass
        return

    order = candidates[0]
    expected = order.get("expected_amount_uzs") or order["price_uzs"]
    short = max(0, expected - amount)
    cart_id = order.get("cart_id")
    who = order.get("username") and f"@{order['username']}" or f"id {order['user_id']}"
    what = f"корзина {cart_id}" if cart_id else f"заказ #{order['id']}"

    # Ровно цена, надбавки у заказа нет (например Premium на 1 месяц — его
    # владелец покупает руками). Это НЕ недоплата, и пугать клиента нечем.
    if short <= 0:
        b = InlineKeyboardBuilder()
        if cart_id:
            b.button(text=f"✅ Подтвердить ({what})", callback_data=f"admin:approve_cart:{cart_id}")
        else:
            b.button(text=f"✅ Подтвердить (#{order['id']})", callback_data=f"admin:approve:{order['id']}")
        b.button(text="🚫 Не наш платёж", callback_data="admin:sms_ignore")
        b.adjust(1)
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"💰 <b>Пришло {format_uzs(amount)} — подходит под {what}</b>\n\n"
                    f"{order['item_name']} · от {who} · получатель {order['recipient']}\n\n"
                    "Сумма ровная (без надбавки), поэтому автоматически не подтверждаю — "
                    "сверь с чеком и нажми кнопку.",
                    reply_markup=b.as_markup(),
                )
            except Exception:
                pass
        return

    # --- Клиенту: сколько доплатить ---
    if short > 0:
        # Запоминаем ожидаемую доплату: без этого отдельный перевод на 207 сум
        # пришёл бы в никуда, а мы уже пообещали, что заказ продолжится сам.
        try:
            await remember_topup(order["id"], short)
        except Exception:
            pass
        lang = await get_user_language(order["user_id"]) or "uz"
        if lang not in ("uz", "ru", "en"):
            lang = "uz"
        try:
            await bot.send_message(
                order["user_id"],
                t(lang, "underpay_notice").format(
                    paid=format_uzs(amount),
                    short=format_uzs(short),
                    total=format_uzs(expected),
                    card=config.PAYMENT_CARD_NUMBER,
                ),
            )
        except Exception:
            pass  # клиент мог закрыть чат — админ всё равно всё увидит

    # --- Админу: карточка с решением ---
    b = InlineKeyboardBuilder()
    if cart_id:
        b.button(text=f"✅ Принять как есть ({what})", callback_data=f"admin:approve_cart:{cart_id}")
    else:
        b.button(text=f"✅ Принять как есть (#{order['id']})", callback_data=f"admin:approve:{order['id']}")
    b.button(text="🚫 Не наш платёж", callback_data="admin:sms_ignore")
    b.adjust(1)

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💰 <b>Недоплата по {what}</b>\n\n"
                f"Пришло: <b>{format_uzs(amount)}</b>\n"
                f"Ждём: <b>{format_uzs(expected)}</b>\n"
                f"Не хватает: <b>{format_uzs(short)}</b>\n\n"
                f"{order['item_name']} · от {who} · получатель {order['recipient']}\n\n"
                "Клиенту уже написал, сколько доплатить. Если недостача копеечная — "
                "жми «Принять как есть», заказ выполнится как обычно.",
                reply_markup=b.as_markup(),
            )
        except Exception:
            pass


# Как банки пишут валюту. БАГ БЫЛ ЗДЕСЬ: латинского "sum" в списке не было,
# хотя именно так пишет большинство узбекских банков ("Summa: 182 067 sum") —
# такие уведомления не распознавались вообще.
# Апострофы в "so'm" бывают четырёх видов: обычный ('), ‘, ’ (автозамена на
# телефоне) и ʻ (правильная узбекская буква). Пропустить любой из них — значит
# не распознать сумму вообще.
_CURRENCY = r"(?:so[\u0027\u2018\u2019\u02bb]?m|som|sum|сум|сўм|сум|uzs)"

# (?![\w'‘]) — чтобы "sum" не срабатывало на слове "Summa".
# БАГ БЫЛ ЗДЕСЬ: в однострочной SMS "8600****2726 Summa: 182 067 sum" бот
# читал "2726 Summa" как «2726 сум» и брал суммой последние 4 цифры карты —
# такая оплата не совпадала ни с одним заказом.
_AMOUNT_RE = re.compile(
    r"([\d][\d\s.,]*\d|\d)\s*" + _CURRENCY + r"(?![\w'‘])", re.IGNORECASE
)

# Значки прихода/расхода. У банковских уведомлений в Telegram знак несёт
# смысл надёжнее слов: зелёный кружок и плюс — деньги пришли, красный и
# минус — ушли. Поэтому знак проверяется РАНЬШЕ ключевых слов.
# Слова про ОСТАТОК на карте. Это не сумма операции, и принимать её за платёж
# нельзя: у части банков остаток стоит в тексте раньше самой суммы.
BALANCE_WORDS = (
    "ostatok", "balans", "dostupno", "остаток", "баланс", "доступно",
    "qoldiq", "balance", "available", "💵",
)

INCOME_MARKS = ("🟢", "✅", "➕")
OUTGOING_MARKS = ("🔴", "🔻", "➖", "❌")

# Слова, означающие ПОСТУПЛЕНИЕ денег на карту.
# "perevod na kartu" — это именно приход (перевод НА твою карту), так пишет
# уведомление UZCARD2UZCARD.
INCOME_WORDS = (
    "popolnen", "postuplen", "prihod", "prixod", "zachislen",
    "perevod na kartu", "перевод на карту", "перевод от",
    "пополнен", "поступлен", "приход", "зачислен",
    "kirim", "tushdi", "tushum", "keldi", "qabul qilindi",
    "income", "credited", "received",
)

# Слова, означающие СПИСАНИЕ (покупка в магазине, оплата услуг, перевод С
# карты). Такие уведомления оплатой заказа быть не могут — игнорируем молча.
OUTGOING_WORDS = (
    "pokupka", "oplata", "spisan", "snyatie", "vydacha",
    "perevod s karty", "perevod so scheta", "перевод с карты", "перевод со счета",
    "покупка", "оплата", "списан", "снятие", "выдача",
    "xarid", "to'lov", "tolov", "yechib", "yechildi", "chiqim",
    "purchase", "payment", "withdraw", "debited", "debit",
)


def _parse_amount(text: str) -> int | None:
    """
    Достаёт сумму ПОСТУПЛЕНИЯ.

    ВАЖНО про формат уведомлений в Telegram: в них обычно ДВЕ суммы —
    сама операция и остаток на карте:

        🟢 Perevod na kartu
        ➕ 1 000.00 UZS      <- это нам нужно
        💳 ***2726
        💵 6 344.10 UZS      <- а это остаток, его брать нельзя

    Поэтому сначала ищем сумму в строке со знаком прихода (➕ / + / 🟢), и
    только если такой строки нет — берём первую сумму в тексте.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    candidates = [ln for ln in lines if any(m in ln for m in INCOME_MARKS) or "+" in ln]

    # Запасной путь (в тексте нет строки со знаком прихода): берём первую сумму,
    # но СНАЧАЛА выкидываем строки про остаток на карте. У части банков остаток
    # идёт выше суммы операции — и без этой чистки бот сравнивал с заказами
    # баланс карты вместо платежа.
    rest = [ln for ln in lines if not any(w in ln.lower() for w in BALANCE_WORDS)]

    for line in candidates + rest + [text]:
        match = _AMOUNT_RE.search(line)
        if match:
            raw = match.group(1).strip()
            # Копейки отбрасываем: "1 000.00 UZS" — это 1000, а не 100 000.
            # Разделитель тысяч ("1.234.567") не пострадает — там 3 цифры.
            raw = re.sub(r"[.,]\d{1,2}$", "", raw)
            digits = re.sub(r"[^\d]", "", raw)
            if digits:
                return int(digits)
    return None


# Замаскированный номер карты: "***2726", "•••• 2726", "8600****2726".
# Ищем именно маску, а не любые 4 цифры подряд — иначе «2726» могло бы
# совпасть с куском суммы, времени или номера операции.
_MASKED_CARD_RE = re.compile(r"[*••xX×]{2,}\s*[-–—]?\s*(\d{4})\b")


def _card_matches(text: str) -> bool:
    """
    СТРОГАЯ проверка, что деньги пришли именно на карту магазина.

    Если SMS_CARD_LAST4 задан, подтверждаем заказ только когда в уведомлении
    действительно есть замаскированная карта и её последние 4 цифры совпали.
    Нет карты в тексте — считаем, что это не наш платёж, и НЕ реагируем:
    лучше попросить чек, чем подтвердить заказ по чужому поступлению.
    """
    last4 = (config.SMS_CARD_LAST4 or "").strip()
    if not last4:
        return True  # проверка выключена — старое поведение

    found = _MASKED_CARD_RE.findall(text)
    if not found:
        return False
    return last4 in found


def _looks_outgoing(text: str) -> bool:
    """Расход: по значку/минусу перед суммой или по ключевому слову."""
    low = text.lower()
    if any(m in text for m in OUTGOING_MARKS):
        return True
    if re.search(r"[-−–]\s?\d[\d\s.,]*\s*" + _CURRENCY, low):
        return True
    # Значок прихода перевешивает слова: у некоторых банков в одном тексте
    # встречается и "oplata" (назначение платежа), и зелёный плюс.
    if any(m in text for m in INCOME_MARKS):
        return False
    return any(w in low for w in OUTGOING_WORDS)


def _looks_income(text: str) -> bool:
    low = text.lower()
    if any(m in text for m in INCOME_MARKS):
        return True
    if any(w in low for w in INCOME_WORDS):
        return True
    return bool(re.search(r"\+\s?\d[\d\s.,]*\s*" + _CURRENCY, low))


def _is_sms_relay_chat(message: Message) -> bool:
    return bool(config.SMS_RELAY_CHAT_ID) and message.chat.id == config.SMS_RELAY_CHAT_ID


@router.message(F.func(_is_sms_relay_chat))
async def handle_sms_relay(message: Message, bot: Bot):
    text = message.text or message.caption or ""

    # ЗАЩИТА ОТ ВЫСТРЕЛА В НОГУ: этот роутер подключён первым и ловит ВСЁ, что
    # пишут в SMS-чат. Если SMS_RELAY_CHAT_ID случайно окажется твоей личной
    # перепиской с ботом, без этой проверки перестали бы работать /start,
    # /admin и остальные команды. SkipHandler отдаёт сообщение дальше по
    # цепочке роутеров, как будто этого обработчика тут нет.
    if text.startswith("/"):
        raise SkipHandler()

    if not config.UNIQUE_AMOUNT_ENABLED:
        raise SkipHandler()

    # 1) Расход (твоя покупка в магазине и т.п.) — не оплата заказа, выходим
    #    сразу и НИЧЕГО админу не пишем. Это и была причина лишних уведомлений.
    if _looks_outgoing(text):
        print(f"[SMS] пропущено (списание, не поступление): {text[:120]!r}", flush=True)
        return

    # 2) Если включён строгий режим — нужна явная пометка о поступлении
    if config.SMS_INCOME_ONLY and not _looks_income(text):
        print(f"[SMS] пропущено (не похоже на поступление): {text[:120]!r}", flush=True)
        return

    # 3) Деньги пришли не на карту магазина — не наш платёж
    if not _card_matches(text):
        print(f"[SMS] пропущено (другая карта, ждём ***{config.SMS_CARD_LAST4}): {text[:120]!r}", flush=True)
        return

    amount = _parse_amount(text)
    if amount is None:
        return  # не нашли сумму — не похоже на уведомление о поступлении

    order = await get_order_by_expected_amount(amount)
    if not order:
        # Уникальная сумма не совпала. Прежде чем сдаваться — проверяем самый
        # частый случай: клиент перевёл КРУГЛУЮ цену (11 000 вместо 11 137),
        # не обратив внимания на просьбу отправить точную сумму. Деньги
        # пришли, заказ ждёт, а бот раньше просто писал «не совпала».
        # Это ДОПЛАТА по заказу, которому в прошлый раз не хватило? Маленький
        # отдельный перевод (207 сум) не совпадает ни с ценой, ни с суммой
        # заказа — узнать его можно только по тому, что мы сами эту доплату
        # и попросили.
        topup = await find_topup_order(amount)
        if topup:
            await clear_topup(topup["id"])
            if topup.get("cart_id"):
                cart_orders = await get_cart_orders(topup["cart_id"])
                await finalize_cart_payment(bot, topup["cart_id"], cart_orders)
                label = f"корзина {topup['cart_id']}"
            else:
                await finalize_payment(bot, topup["id"], topup)
                label = f"Заказ #{topup['id']} ({topup['item_name']})"
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"🤖✅ {label} подтверждён: клиент доплатил недостающие {amount} сум.",
                    )
                except Exception:
                    pass
            return

        # ПОРЯДОК ЗДЕСЬ ВАЖЕН.
        #
        # Сначала — ТОЧНОЕ совпадение с ценой товара. У позиций без надбавки
        # (Premium на 1 месяц) сумма к оплате равна цене, и такой платёж
        # принадлежит именно этому заказу. Раньше этот случай проверялся
        # последним, и перевод на 49 000 сначала попадал в «недоплату» по
        # ЧУЖОМУ старому заказу, который ждал 49 219 — бот писал о доплате
        # не тому человеку.
        #
        # И только потом — догадка про округление вниз (ждали 11 207,
        # прислали 11 000). Она нестрогая, поэтому идёт после точной.
        window = config.SMS_MATCH_WINDOW_HOURS
        candidates = await find_orders_by_base_price(amount, within_hours=window)
        if not candidates:
            candidates = await find_underpaid_orders(
                amount, config.SMS_UNDERPAY_MAX_GAP_UZS, within_hours=window
            )

        # Пополнения ищем ЗДЕСЬ ЖЕ и в общей куче с заказами.
        #
        # Раньше пополнения проверялись первыми и с широким допуском — и
        # перевод, сделанный по заказу, «прилипал» к чужому пополнению с
        # похожей суммой: деньги уходили на баланс постороннего человека, а
        # заказ так и висел неоплаченным. Теперь если под сумму подходит
        # больше одного варианта — не решаем сами, показываем админу.
        topups = await find_topup_requests(amount, config.TOPUP_TOLERANCE_UZS, hours=window)

        if len(candidates) + len(topups) > 1:
            await _ask_admin_which_match(bot, amount, candidates, topups)
            return
        if topups:
            await _credit_topup(bot, amount, topups[0])
            return
        if candidates:
            await _handle_underpayment(bot, amount, candidates)
            return

        # Клиент заплатил ПОЗЖЕ, чем мы ждали: заказ уже отменился по таймауту,
        # а деньги пришли. Раньше бот в этом месте просто молчал — и человек
        # оставался без товара и без денег, пока сам не напишет. Теперь такое
        # поступление всегда показываем админу, даже если обычные оповещения
        # о непонятных суммах выключены: это не «непонятная сумма», это
        # конкретный заказ конкретного клиента.
        expired = await find_expired_order_by_amount(amount)
        if expired:
            await _alert_late_payment(bot, amount, expired)
            return

        # Сумма не совпала ни с одним ожидающим заказом — либо это поступление
        # не через бота, либо регулярка выше не подходит под формат банка.
        # Пишем админу ТОЛЬКО если он сам включил эти оповещения.
        print(f"[SMS] поступление {amount} не совпало ни с одним заказом", flush=True)
        if config.SMS_UNMATCHED_ALERTS:
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"🤖 SMS на сумму {amount} не совпала ни с одним заказом "
                        "(или это не оплата заказа).",
                    )
                except Exception:
                    pass
        return

    # Заказ из корзины — подтверждаем всю корзину целиком, одной суммой
    if order.get("cart_id"):
        cart_orders = await get_cart_orders(order["cart_id"])
        await finalize_cart_payment(bot, order["cart_id"], cart_orders)
        label = f"корзина {order['cart_id']} ({len(cart_orders)} тов.)"
    else:
        await finalize_payment(bot, order["id"], order)
        label = f"Заказ #{order['id']} ({order['item_name']})"

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🤖✅ {label} подтверждён автоматически по SMS на сумму {amount}.",
            )
        except Exception:
            pass


async def _alert_late_payment(bot: Bot, amount: int, order: dict) -> None:
    """Деньги пришли по заказу, который уже отменился по таймауту."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from services.prices import format_uzs

    who = order.get("username") and f"@{order['username']}" or f"id {order['user_id']}"
    cart_id = order.get("cart_id")
    what = f"корзина {cart_id}" if cart_id else f"заказ #{order['id']}"

    b = InlineKeyboardBuilder()
    b.button(text=f"✅ Всё равно выполнить ({what})", callback_data=f"sms:revive:{order['id']}")
    b.button(text="🚫 Не наш платёж", callback_data="admin:sms_ignore")
    b.adjust(1)

    print(f"[SMS] поздняя оплата {amount} по отменённому заказу #{order['id']}", flush=True)
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"⌛💰 <b>Пришло {format_uzs(amount)} по УЖЕ ОТМЕНЁННОМУ заказу</b>\n\n"
                f"{what.capitalize()} — {order['item_name']}\n"
                f"От: {who} · получатель: {order['recipient']}\n"
                f"Отменён по таймауту, но сумма совпала точно.\n\n"
                "Скорее всего клиент просто заплатил позже. Нажми «Всё равно "
                "выполнить» — заказ вернётся в работу и выполнится как обычный.",
                reply_markup=b.as_markup(),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("sms:revive:"))
async def revive_late_order(call: CallbackQuery, bot: Bot):
    """Вернуть в работу заказ, отменённый по таймауту, — деньги по нему пришли."""
    if call.from_user.id not in config.ADMIN_IDS:
        await call.answer("Только для админа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    if order["status"] != "rejected":
        await call.answer(f"Заказ #{order_id} уже в работе — ничего не делаю", show_alert=True)
        return

    cart_id = order.get("cart_id")
    if cart_id:
        await set_cart_status(cart_id, "payment_review", "Поздняя оплата по SMS")
        cart_orders = await get_cart_orders(cart_id)
        await finalize_cart_payment(bot, cart_id, cart_orders)
        label = f"корзина {cart_id}"
    else:
        await set_order_status(order_id, "payment_review", "Поздняя оплата по SMS")
        order = await get_order(order_id)
        await finalize_payment(bot, order_id, order)
        label = f"заказ #{order_id}"

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer(f"{label.capitalize()} вернулся в работу")
