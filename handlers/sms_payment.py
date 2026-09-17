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
from aiogram.types import Message

import config
from database.db import get_order_by_expected_amount, get_cart_orders
from handlers.admin import finalize_payment, finalize_cart_payment

router = Router()

# Как банки пишут валюту. БАГ БЫЛ ЗДЕСЬ: латинского "sum" в списке не было,
# хотя именно так пишет большинство узбекских банков ("Summa: 182 067 sum") —
# такие уведомления не распознавались вообще.
_CURRENCY = r"(?:so'?m|so‘m|som|sum|сум|сўм|uzs)"

_AMOUNT_RE = re.compile(r"([\d][\d\s.,]*\d|\d)\s*" + _CURRENCY, re.IGNORECASE)

# Значки прихода/расхода. У банковских уведомлений в Telegram знак несёт
# смысл надёжнее слов: зелёный кружок и плюс — деньги пришли, красный и
# минус — ушли. Поэтому знак проверяется РАНЬШЕ ключевых слов.
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
    for line in candidates + [text]:
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
