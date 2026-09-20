"""
Корзина: несколько товаров — одна оплата.

Раньше в мини-аппе можно было купить строго ОДИН товар за раз: выбрал звёзды —
оформил — оплатил, захотел ещё премиум — всё сначала, вторая карта, второй чек.
Теперь товары складываются в корзину и оплачиваются одной суммой.

Как это устроено внутри (важно для понимания остального кода):
- каждый товар корзины становится ОБЫЧНОЙ строкой в таблице orders — поэтому
  выполнение (звёзды/подарки/премиум), история заказов, статистика и рейтинг
  работают ровно так же, как и для одиночных заказов, ничего не переписано;
- все строки одной корзины связаны общим cart_id и имеют ОДИНАКОВУЮ
  expected_amount_uzs (сумма всей корзины) — чек, подтверждение админом и
  автоподтверждение по SMS работают на корзину целиком.

Аренда NFT в корзину НЕ кладётся: у неё свой отдельный сценарий (срок, комиссия
сети, tc://-ссылка для подключения), смешивать его с обычными товарами в одной
оплате — верный способ запутать и клиента, и админа.
"""

import uuid

from aiogram import Bot
from aiogram.fsm.context import FSMContext

from database.db import (
    create_order, allocate_and_set_expected_amount, get_user_language,
    upsert_user,
)
from handlers.states import OrderStates
from services.i18n import t
from services.prices import format_uzs, STARS_MIN, STARS_MAX

# Что вообще можно положить в корзину
CART_CATEGORIES = ("stars", "stars_custom", "premium", "simple_gift")

MAX_CART_LINES = 20        # разных позиций в корзине
MAX_LINE_QTY = 10          # штук одной позиции
MAX_TOTAL_UZS = 100_000_000  # защита от мусорных/подменённых цен


class CartError(Exception):
    """Корзина не прошла проверку — текст ошибки уходит в мини-апп как есть."""


def _as_int(value, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise CartError(f"bad_{field}")


def normalize_lines(raw_lines, user_id: int, username: str | None) -> list[dict]:
    """
    Приводит корзину из мини-аппа к строкам заказов.

    Одна позиция корзины не всегда = одна строка заказа:
    - звёзды с количеством N складываются в ОДИН заказ на N*amount звёзд —
      получателю это придёт одной транзакцией Fragment, а не N подряд;
    - Premium с количеством N — это N отдельных заказов (3 месяца ×2 ≠ 6
      месяцев, объединять нельзя);
    - подарки с количеством N — один заказ с quantity=N, отправку N раз
      подряд бот уже умеет (см. services/telegram_gifts.fulfill_simple_gift).
    """
    if not isinstance(raw_lines, list) or not raw_lines:
        raise CartError("empty_cart")
    if len(raw_lines) > MAX_CART_LINES:
        raise CartError("too_many_items")

    rows: list[dict] = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            raise CartError("bad_item")

        category = raw.get("category")
        if category not in CART_CATEGORIES:
            raise CartError("bad_category")

        qty = max(1, min(_as_int(raw.get("quantity", 1) or 1, "quantity"), MAX_LINE_QTY))
        unit_price = _as_int(raw.get("price", 0), "price")
        if unit_price <= 0:
            raise CartError("bad_price")

        # Получатель: "себе" — берём @username с сервера (данные клиента бывают
        # пустыми из-за кэша WebView), "другу" — то, что ввёл человек.
        recipient_type = raw.get("recipient_type", "self")
        recipient = (raw.get("recipient") or "").strip()
        recipient_user_id = None
        if recipient_type == "self" or not recipient:
            recipient = f"@{username}" if username else ""
            recipient_user_id = user_id
        if recipient and not recipient.startswith("@"):
            recipient = "@" + recipient
        if not recipient:
            raise CartError("no_username")

        note = (raw.get("note") or "").strip() or None
        base = {
            "recipient": recipient,
            "recipient_user_id": recipient_user_id,
            "note": note,
        }

        if category in ("stars", "stars_custom"):
            stars_amount = _as_int(raw.get("stars_amount") or raw.get("quantity_stars") or 0, "stars")
            if stars_amount <= 0:
                raise CartError("bad_stars")
            total_stars = stars_amount * qty
            # Fragment принимает только 50..1 000 000 звёзд за раз. Раньше этой
            # проверки не было, и заказ на 10 млн звёзд спокойно создавался,
            # оплачивался — и падал уже на выполнении, зависая навсегда.
            if not (STARS_MIN <= total_stars <= STARS_MAX):
                raise CartError("stars_limit")
            rows.append({
                **base,
                "category": "stars",
                "item_name": f"{total_stars} звёзд",
                "quantity": total_stars,
                "price_uzs": unit_price * qty,
            })

        elif category == "premium":
            for _ in range(qty):
                rows.append({
                    **base,
                    "category": "premium",
                    "item_name": raw.get("item_name") or "Premium",
                    "quantity": 1,
                    "price_uzs": unit_price,
                })

        elif category == "simple_gift":
            gift_id = str(raw.get("gift_id") or "").strip()
            if not gift_id:
                raise CartError("bad_gift")
            rows.append({
                **base,
                "category": "simple_gift",
                "item_name": raw.get("item_name") or "Подарок",
                "quantity": qty,
                "price_uzs": unit_price * qty,
                "nft_address": gift_id,  # то же поле переиспользуется под gift_id
            })

    total = sum(r["price_uzs"] for r in rows)
    if total <= 0 or total > MAX_TOTAL_UZS:
        raise CartError("bad_total")
    return rows


def summary_text(rows: list[dict], lang: str | None) -> str:
    """Список товаров корзины для сообщения в чате — по строке на товар."""
    lines = []
    for r in rows:
        qty_note = f" ×{r['quantity']}" if r["category"] == "simple_gift" and r["quantity"] > 1 else ""
        lines.append(f"• {r['item_name']}{qty_note} → {r['recipient']} — {format_uzs(r['price_uzs'])}")
    return "\n".join(lines)


async def process_cart_order(
    bot: Bot,
    state: FSMContext,
    user_id: int,
    username: str | None,
    full_name: str,
    items,
) -> dict:
    """
    Проверяет корзину и показывает клиенту в чате ОДНО сообщение со списком
    товаров и общей суммой ("Всё верно?"). Сам заказ создаётся только после
    нажатия «Подтвердить» — точно так же, как для одиночного заказа.
    """
    await upsert_user(user_id, username or "", full_name)
    rows = normalize_lines(items, user_id, username)
    total = sum(r["price_uzs"] for r in rows)

    await state.update_data(cart_rows=rows, cart_total=total)
    await state.set_state(OrderStates.confirming_cart)

    lang = await get_user_language(user_id)
    from keyboards.user_kb import confirm_cart_kb

    await bot.send_message(
        user_id,
        f"🛒 <b>{t(lang, 'cart_check_title')}</b>\n\n"
        f"{summary_text(rows, lang)}\n\n"
        f"{t(lang, 'order_check_total')}: <b>{format_uzs(total)}</b>\n\n"
        f"{t(lang, 'order_check_confirm')}",
        reply_markup=confirm_cart_kb(),
    )
    return {"lines": len(rows), "total": total}


async def place_cart_order_direct(
    bot: Bot,
    state: FSMContext,
    user_id: int,
    username: str | None,
    full_name: str,
    items,
) -> dict:
    """
    Оформление корзины ПРЯМО ИЗ ВИТРИНЫ, без шага «Всё верно?» в чате:
    человек уже видел список и сумму в самой корзине. Заказы создаются сразу,
    а витрина дальше сама ведёт его по статусам. В чат уходит сообщение с
    составом и реквизитами — для истории и чтобы чек можно было прислать туда.
    """
    import config
    from keyboards.user_kb import payment_methods_kb

    await upsert_user(user_id, username or "", full_name)
    rows = normalize_lines(items, user_id, username)
    created = await create_cart_orders(rows, user_id, username)

    # Состояние как после подтверждения в чате — чек, присланный в бота
    # сообщением, обработается как обычно (см. handlers/payment.py).
    await state.update_data(
        cart_id=created["cart_id"],
        order_id=created["order_ids"][0],
        cart_order_ids=created["order_ids"],
    )
    await state.set_state(OrderStates.waiting_payment_proof)

    lang = await get_user_language(user_id)
    amount_note = ""
    if config.UNIQUE_AMOUNT_ENABLED and created["pay_amount"] != created["total"]:
        amount_note = (
            f"\n\n⚠️ {t(lang, 'cart_exact_amount')} <b>{format_uzs(created['pay_amount'])}</b>"
            + t(lang, "pay_commission_note")
        )

    try:
        await bot.send_message(
            user_id,
            f"🛒 <b>{t(lang, 'cart_created_title')}</b>\n\n"
            f"{summary_text(rows, lang)}\n\n"
            f"{t(lang, 'order_check_total')}: <b>{format_uzs(created['total'])}</b>\n\n"
            + t(lang, "order_pay_card")
            + f"<code>{config.PAYMENT_CARD_NUMBER}</code>\n"
            + f"{t(lang, 'order_pay_receiver')}: {config.PAYMENT_CARD_HOLDER}"
            + amount_note
            + "\n"
            + t(lang, "order_pay_hint_webapp"),
            reply_markup=payment_methods_kb(),
        )
    except Exception:
        pass  # чат не критичен: клиента дальше ведёт витрина

    return {
        "cart_id": created["cart_id"],
        "order_id": created["order_ids"][0],
        "order_ids": created["order_ids"],
        "price_uzs": created["total"],
        "pay_amount": created["pay_amount"],
        "lines": len(rows),
    }


async def create_cart_orders(rows: list[dict], user_id: int, username: str | None) -> dict:
    """
    Создаёт строки заказов одной корзины и выдаёт ОДНУ сумму к оплате на всех.
    -> {"cart_id": str, "order_ids": [int], "total": int, "pay_amount": int}
    """
    import config

    cart_id = uuid.uuid4().hex[:10]
    total = sum(r["price_uzs"] for r in rows)
    order_ids = []

    for r in rows:
        order_id = await create_order(
            user_id=user_id,
            username=username or "",
            category=r["category"],
            item_name=r["item_name"],
            quantity=r.get("quantity", 1),
            price_uzs=r["price_uzs"],
            recipient=r["recipient"],
            recipient_user_id=r.get("recipient_user_id"),
            nft_address=r.get("nft_address"),
            cart_id=cart_id,
        )
        order_ids.append(order_id)

    # Уникальная сумма выдаётся на ВСЮ корзину и проставляется каждой её строке —
    # так автоподтверждение по SMS находит корзину по одной сумме поступления.
    pay_amount = total
    if config.UNIQUE_AMOUNT_ENABLED:
        # Вся корзина получает одну сумму, и закрепляется она за всеми строками
        # сразу — одной транзакцией, чтобы параллельный заказ не забрал ту же.
        pay_amount = await allocate_and_set_expected_amount(
            order_ids, total, config.UNIQUE_AMOUNT_MAX_OFFSET
        )
    else:
        from database.db import set_expected_amount
        for order_id in order_ids:
            await set_expected_amount(order_id, pay_amount)

    return {"cart_id": cart_id, "order_ids": order_ids, "total": total, "pay_amount": pay_amount}
