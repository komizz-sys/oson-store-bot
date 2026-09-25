"""
Лёгкий HTTP-сервер, работающий в ТОМ ЖЕ процессе, что и сам бот (bot.py), —
поэтому имеет прямой доступ к той же базе данных без танцев с общими volume
на Railway (Railway не умеет шарить один volume между двумя разными сервисами).

Два вида эндпоинтов:
- /internal/stats — закрытый секретом, только для отдельного бота-аналитика
  (см. ANALYTICS_API_SECRET в .env — должен совпадать в обоих ботах).
- /public/* — открытые, их дёргает мини-апп магазина (Tarix/TOP/Profil).
  Личные данные (история заказов, своя статистика) отдаются только после
  проверки подписи Telegram initData — иначе можно было бы подставить чужой
  user_id и увидеть заказы другого человека.
"""

from aiohttp import web
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

import base64
import config
import gzip
import logging
import re

from database.db import (
    get_revenue_stats, get_user_orders, get_user_spend_stats, get_leaderboard,
    get_leaderboard_position,
    get_pending_rent_link_order, set_rent_link, get_order, set_order_status,
    attach_payment_proof, get_cart_orders, set_cart_status, attach_cart_payment_proof,
    find_order_by_receipt, set_receipt_fingerprint, set_cart_receipt_fingerprint,
    count_pending_orders,
)

# Тот же формат ссылки, что принимает обработчик в чате (handlers/rent_link.py)
_RENT_LINK_RE = re.compile(r"^(tc://\S+|https?://\S+|t\.me/\S+)$", re.IGNORECASE)
from services.telegram_auth import validate_init_data
from services.order_processing import process_order, OrderError

# Заполняются в start_stats_server() — нужны для /public/create_order,
# чтобы вручную собрать FSMContext вне обычного апдейта от aiogram
# (тот же Storage, что использует Dispatcher, поэтому дальнейшее
# подтверждение/отмена заказа кнопками в чате работает как обычно).
_bot = None
_storage = None

# Когда по заказу последний раз уходила просьба об отмене (order_id -> монотонное
# время). Живёт в памяти процесса: если бот перезапустится, максимум придёт одно
# лишнее сообщение — ради этого городить таблицу в базе незачем.
_CANCEL_REQUEST_SENT: dict[int, float] = {}
_CANCEL_REQUEST_COOLDOWN = 15 * 60  # секунд

PERIOD_TO_SQL = {
    "today": "datetime('now', 'start of day')",
    "week": "datetime('now', '-7 day')",
    "month": "datetime('now', '-30 day')",
    "all": None,
}


async def _period_since_sql(period: str) -> str | None:
    if PERIOD_TO_SQL.get(period) is None:
        return None
    import aiosqlite
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(f"SELECT {PERIOD_TO_SQL[period]}") as cur:
            return (await cur.fetchone())[0]


async def handle_stats(request: web.Request) -> web.Response:
    if not config.ANALYTICS_API_SECRET:
        return web.json_response({"error": "ANALYTICS_API_SECRET не задан на сервере магазина"}, status=503)

    if request.headers.get("X-Internal-Secret") != config.ANALYTICS_API_SECRET:
        return web.json_response({"error": "forbidden"}, status=403)

    period = request.query.get("period", "today")
    if period not in PERIOD_TO_SQL:
        return web.json_response({"error": f"unknown period, expected one of {list(PERIOD_TO_SQL)}"}, status=400)

    since_sql = await _period_since_sql(period)
    data = await get_revenue_stats(since_sql, config.TON_GRAM_RATE_UZS)
    data["period"] = period
    return web.json_response(data)


def _extract_verified_user(pairs: dict) -> dict | None:
    init_data = pairs.get("initData") if isinstance(pairs, dict) else None
    return validate_init_data(init_data, config.BOT_TOKEN)


async def handle_my_orders(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = _extract_verified_user(body)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    orders = await get_user_orders(user["id"])
    return web.json_response({"orders": orders})


async def handle_my_stats(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = _extract_verified_user(body)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    stats = await get_user_spend_stats(user["id"])
    return web.json_response(stats)


async def handle_active_order(request: web.Request) -> web.Response:
    """
    Активный (ещё не завершённый) заказ клиента — чтобы витрина могла показать
    "у вас есть заказ в работе" после перезахода, и понять, не ждём ли мы от
    него ссылку для аренды. Реальные статусы из БД, ничего не выдумываем.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    orders = await get_user_orders(user["id"])
    active = next(
        (o for o in orders if o["status"] in ("awaiting_payment", "payment_review", "paid", "fulfilling")),
        None,
    )
    if not active:
        return web.json_response({"active": None})

    # Заказ из корзины — показываем её ЦЕЛИКОМ одной карточкой с общей суммой,
    # иначе клиент увидел бы только один товар из пяти и не понял, что платить.
    cart_items = []
    if active.get("cart_id"):
        cart_orders = await get_cart_orders(active["cart_id"])
        if cart_orders:
            cart_items = [
                {"item_name": o["item_name"], "price_uzs": o["price_uzs"], "recipient": o["recipient"]}
                for o in cart_orders
            ]
            active = dict(
                active,
                price_uzs=sum(o["price_uzs"] for o in cart_orders),
                item_name=f"🛒 {len(cart_orders)}",
            )

    # Ждём ли от клиента tc://-ссылку для подключения аренды.
    # Для ПРОДЛЕНИЯ ссылка не нужна — подарок уже подключён к профилю.
    needs_link = bool(
        active["category"] == "nft_rent"
        and active["status"] == "paid"
        and not active.get("is_extension")
        and not (active.get("rent_link") or "")
    )
    # Реквизиты нужны, только пока клиент ещё не оплатил — чтобы он мог
    # оплатить и приложить чек не выходя из витрины.
    needs_payment = active["status"] == "awaiting_payment"

    return web.json_response({
        "active": {
            "id": active["id"],
            "category": active["category"],
            "item_name": active["item_name"],
            "price_uzs": active["price_uzs"],
            "status": active["status"],
            "cart_id": active.get("cart_id"),
            "cart_items": cart_items,
            "needs_rent_link": needs_link,
            "needs_payment": needs_payment,
            "card_number": config.PAYMENT_CARD_NUMBER if needs_payment else None,
            "card_holder": config.PAYMENT_CARD_HOLDER if needs_payment else None,
        }
    })


async def handle_submit_rent_link(request: web.Request) -> web.Response:
    """
    Приём tc://-ссылки прямо из витрины (раньше клиент присылал её в чат боту).
    Сразу пытаемся подключить аренду через marketapp — тем же методом, что и
    обработчик в чате, чтобы логика не разъехалась.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _banned_response(user["id"])
    if blocked is not None:
        return blocked

    link = (body.get("link") or "").strip()
    if not _RENT_LINK_RE.match(link):
        return web.json_response({"error": "bad_link"}, status=400)

    from services.rent_connect import submit_rent_link

    # «Qayta ulash» у конкретной аренды в витрине приходит с order_id.
    # Без него — первая ссылка после оплаты, либо новая взамен умершей.
    req_order_id = _order_id_from(body)
    if req_order_id:
        from services.rent_connect import relink_rental
        result = await relink_rental(_bot, user["id"], req_order_id, link)
    else:
        result = await submit_rent_link(_bot, user["id"], link, announce_start=False)
    if result is None:
        return web.json_response({"error": "no_pending_order"}, status=400)
    if result.get("choose"):
        return web.json_response({"error": "choose_rental"}, status=400)
    order = result["order"]
    return web.json_response({
        "ok": True,
        "connected": result["connected"],
        "pending": not result["connected"],
        "reconnect": result["reconnect"],
        "item_name": order["item_name"],
        "order_id": order["id"],
    })


async def _send_platform_video(request: web.Request) -> web.Response:
    """
    Прислать в чат видео-инструкцию для телефона клиента и дать витрине
    закрыться — человек сразу оказывается там, куда пришло видео.

    platform приходит из витрины (кнопка «Android» / «iPhone»); если не
    пришла — берём то, что сообщил Telegram (tg.platform).
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    platform = "android" if "android" in str(body.get("platform") or "").lower() else "ios"
    from services.rent_link import send_tutorial_video

    try:
        await send_tutorial_video(_bot, user["id"], platform)
    except Exception:
        return web.json_response({"ok": False, "error": "send_failed"}, status=502)
    return web.json_response({"ok": True})


# Две старые кнопки витрины («как получить ссылку» и «как показать в профиле»)
# ведут на одно и то же: видео показывает оба шага, отличается только телефон.
handle_send_rent_tutorial = _send_platform_video
handle_send_display_video = _send_platform_video


async def handle_balance(request: web.Request) -> web.Response:
    """Остаток и последние операции — для вкладки «Профиль» в витрине."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    from database.db import get_balance, get_balance_history, get_pending_topup

    balance = await get_balance(user["id"])
    history = await get_balance_history(user["id"], limit=10)
    pending = await get_pending_topup(user["id"])
    return web.json_response({
        "balance": balance,
        "history": history,
        "pending_topup": (
            {"expected": pending["expected_uzs"], "created_at": pending["created_at"]}
            if pending else None
        ),
        "card_number": config.PAYMENT_CARD_NUMBER,
        "card_holder": config.PAYMENT_CARD_HOLDER,
        "min_uzs": config.TOPUP_MIN_UZS,
        "max_uzs": config.TOPUP_MAX_UZS,
    })


async def handle_create_topup(request: web.Request) -> web.Response:
    """
    Заявка на пополнение: выдаём сумму с уникальным хвостом.

    Хвост — единственный способ понять, чей это перевод: SMS от банка
    сообщает сумму, но не отправителя. При этом на баланс потом зачисляется
    РОВНО столько, сколько реально пришло, — комиссия банка просто уменьшает
    зачисление и ничего не ломает.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _banned_response(user["id"])
    if blocked is not None:
        return blocked

    try:
        amount = int(body.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount < config.TOPUP_MIN_UZS or amount > config.TOPUP_MAX_UZS:
        return web.json_response({"error": "bad_amount"}, status=400)

    from database.db import create_topup_request, get_pending_topup, get_user_language

    # Одна открытая заявка на человека: иначе по двум почти одинаковым суммам
    # станет невозможно понять, какое из пополнений оплатили.
    existing = await get_pending_topup(user["id"])
    if existing:
        # Заявка уже есть. Молча подменять запрошенную сумму на старую нельзя:
        # человек просил 500 000, получал в ответ 20 123, переводил 500 000 —
        # и деньги не совпадали ни с чем. Говорим прямо и даём отменить.
        return web.json_response({
            "ok": False,
            "error": "already_pending",
            "expected": existing["expected_uzs"],
            "card_number": config.PAYMENT_CARD_NUMBER,
            "card_holder": config.PAYMENT_CARD_HOLDER,
        }, status=409)
    else:
        created = await create_topup_request(
            user["id"], amount, config.UNIQUE_AMOUNT_MAX_OFFSET
        )

    lang = await get_user_language(user["id"]) or "uz"
    if lang not in ("uz", "ru", "en"):
        lang = "uz"

    # Дублируем в чат: там реквизиты не потеряются, когда витрина закроется.
    try:
        from services.i18n import t as _t
        from services.prices import format_uzs as _fmt

        await _bot.send_message(
            user["id"],
            _t(lang, "topup_created").format(
                amount=_fmt(created["expected"]),
                card=config.PAYMENT_CARD_NUMBER,
                holder=config.PAYMENT_CARD_HOLDER,
            ),
        )
    except Exception:
        pass

    return web.json_response({
        "ok": True,
        "expected": created["expected"],
        "card_number": config.PAYMENT_CARD_NUMBER,
        "card_holder": config.PAYMENT_CARD_HOLDER,
    })


async def handle_pay_from_balance(request: web.Request) -> web.Response:
    """
    Оплатить заказ с баланса.

    Деньги уже у магазина, поэтому сверять нечего. Всё денежное —
    проверка статуса, списание и перевод заказа в «оплачен» — делается ОДНОЙ
    транзакцией в pay_order_from_balance: иначе двойной тап по кнопке
    списывал деньги дважды и заказ выполнялся дважды за счёт магазина.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _banned_response(user["id"])
    if blocked is not None:
        return blocked

    order_id = _order_id_from(body)
    order = await get_order(order_id)
    if not order or order["user_id"] != user["id"]:
        return web.json_response({"error": "not_found"}, status=404)

    from database.db import (
        get_balance, get_user_language, pay_order_from_balance, refund_to_balance,
    )

    cart_id = order.get("cart_id")
    if cart_id:
        cart_orders = await get_cart_orders(cart_id)
        price = sum(o["price_uzs"] for o in cart_orders)
    else:
        cart_orders = []
        price = order["price_uzs"]

    result = await pay_order_from_balance(order_id, user["id"], price, cart_id)
    if result != "ok":
        status = 409 if result == "busy" else 400
        return web.json_response(
            {"error": result, "balance": await get_balance(user["id"]), "need": price},
            status=status,
        )

    left = await get_balance(user["id"])
    label = f"корзина {cart_id}" if cart_id else f"заказ #{order_id}"
    lang = await get_user_language(user["id"]) or "uz"
    if lang not in ("uz", "ru", "en"):
        lang = "uz"

    from services.i18n import t as _t
    from services.prices import format_uzs as _fmt

    try:
        await _bot.send_message(
            user["id"],
            _t(lang, "paid_from_balance").format(
                order_id=order_id, amount=_fmt(price), balance=_fmt(left)
            ),
        )
    except Exception:
        pass

    for admin_id in config.ADMIN_IDS:
        try:
            await _bot.send_message(
                admin_id,
                f"💼✅ {label.capitalize()} оплачен С БАЛАНСА клиента "
                f"<code>{user['id']}</code> на {_fmt(price)}. Остаток {_fmt(left)}.",
            )
        except Exception:
            pass

    # Дальше — общий путь выполнения. Если он сорвётся, деньги уже списаны,
    # поэтому возвращаем их на баланс и зовём админа: молча забрать оплату и
    # не выполнить заказ — худшее, что магазин может сделать.
    from handlers.admin import finalize_payment, finalize_cart_payment

    try:
        if cart_id:
            await finalize_cart_payment(_bot, cart_id, cart_orders)
        else:
            await finalize_payment(_bot, order_id, await get_order(order_id))
    except Exception as e:
        print(f"[BALANCE] выполнение {label} сорвалось после списания: {e}", flush=True)
        try:
            await refund_to_balance(
                user["id"], price, f"Возврат: не удалось выполнить {label}", order_id
            )
        except Exception:
            pass
        for admin_id in config.ADMIN_IDS:
            try:
                await _bot.send_message(
                    admin_id,
                    f"🛑 {label.capitalize()}: деньги списались, но выполнение "
                    f"сорвалось ({e}). Я вернул {_fmt(price)} на баланс клиента "
                    f"<code>{user['id']}</code>. Разберись вручную.",
                )
            except Exception:
                pass
        return web.json_response({"error": "fulfil_failed", "balance": await get_balance(user["id"])}, status=500)

    return web.json_response({"ok": True, "balance": left})


async def handle_topup_receipt(request: web.Request) -> web.Response:
    """
    Чек о пополнении — и админ сам решает, сколько зачислить.

    Зачем, если есть автозачисление по SMS: по одной сумме в SMS не видно,
    КТО заплатил, а если SMS не дошла или банк написал её непривычно —
    деньги просто висят, и разобраться не по чему. С чеком у владельца
    всегда есть картинка и имя клиента рядом.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _banned_response(user["id"])
    if blocked is not None:
        return blocked

    from database.db import (
        get_pending_topup, find_topup_by_receipt, set_topup_receipt,
    )

    topup = await get_pending_topup(user["id"])
    if not topup:
        return web.json_response({"error": "no_topup"}, status=404)

    image_b64 = body.get("image_base64") or ""
    if not image_b64:
        return web.json_response({"error": "no_image"}, status=400)
    try:
        raw = base64.b64decode(image_b64.split(",")[-1])
    except Exception:
        return web.json_response({"error": "bad_image"}, status=400)
    if len(raw) > 8 * 1024 * 1024:
        return web.json_response({"error": "too_big"}, status=400)

    import hashlib

    fingerprint = "sha256:" + hashlib.sha256(raw).hexdigest()
    dup = await find_topup_by_receipt(fingerprint, exclude_id=topup["id"])
    if dup:
        for admin_id in config.ADMIN_IDS:
            try:
                await _bot.send_message(
                    admin_id,
                    f"🔁 <b>Повторный чек на пополнение</b>\n\n"
                    f"Клиент <code>{user['id']}</code> прислал чек, который уже "
                    f"использовали (пополнение #{dup['id']}). Не зачисляю.",
                )
            except Exception:
                pass
        return web.json_response({"error": "duplicate_receipt"}, status=409)

    await set_topup_receipt(topup["id"], fingerprint)

    from aiogram.types import BufferedInputFile
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from services.prices import format_uzs as _fmt

    who = f"@{user.get('username')}" if user.get("username") else f"id {user['id']}"
    caption = (
        f"💼 <b>Пополнение баланса — чек</b>\n\n"
        f"От: {who} (<code>{user['id']}</code>)\n"
        f"Просил пополнить на: <b>{_fmt(topup['expected_uzs'])}</b>\n\n"
        "Сверь сумму на чеке. Банк удерживает комиссию, поэтому дойти могло "
        "меньше — зачисляй то, что реально пришло."
    )
    b = InlineKeyboardBuilder()
    b.button(
        text=f"✅ Зачислить {_fmt(topup['expected_uzs'])}",
        callback_data=f"topup:credit:{topup['id']}:{topup['expected_uzs']}",
    )
    b.button(text="✏️ Другая сумма", callback_data=f"topup:manual:{topup['id']}")
    b.button(text="🚫 Отклонить", callback_data=f"topup:reject:{topup['id']}")
    b.adjust(1)

    sent_any = False
    for admin_id in config.ADMIN_IDS:
        try:
            await _bot.send_photo(
                admin_id,
                BufferedInputFile(raw, filename=f"topup_{topup['id']}.jpg"),
                caption=caption,
                reply_markup=b.as_markup(),
            )
            sent_any = True
        except Exception as e:
            print(f"[TOPUP] чек не ушёл админу {admin_id}: {e}", flush=True)

    if not sent_any:
        return web.json_response({"error": "send_failed"}, status=500)
    return web.json_response({"ok": True})


async def handle_cancel_topup(request: web.Request) -> web.Response:
    """Отменить своё незакрытое пополнение, чтобы заказать другую сумму."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    from database.db import cancel_topup_request

    await cancel_topup_request(user["id"])
    return web.json_response({"ok": True})


async def handle_cancel_order(request: web.Request) -> web.Response:
    """
    Отмена заказа самим клиентом из витрины.

    Два разных случая, и путать их нельзя:
    - заказ ещё НЕ оплачен (awaiting_payment / payment_review) — клиент
      отменяет его сам, мгновенно: денег у продавца нет, спрашивать нечего;
    - заказ УЖЕ оплачен (paid / fulfilling) — сам клиент отменить не может,
      иначе он одной кнопкой «терял» бы свои же деньги. Вместо отмены уходит
      ЗАПРОС продавцу, тот решает кнопками: отменить или оставить в работе.

    Раньше второго случая не было вовсе, и заказ, который не удалось
    выполнить, навсегда висел у клиента активным и блокировал новые заказы.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    order = await get_order(_order_id_from(body))
    # Проверяем владельца — иначе по чужому id можно было бы отменить чужой заказ
    if not order or order["user_id"] != user["id"]:
        return web.json_response({"error": "not_found"}, status=404)

    if order["status"] in ("awaiting_payment", "payment_review"):
        if order.get("cart_id"):
            # Корзина оплачивается одной суммой — и отменяется только целиком
            await set_cart_status(order["cart_id"], "rejected", "Отменён клиентом")
        else:
            await set_order_status(order["id"], "rejected", "Отменён клиентом")
        return web.json_response({"ok": True, "cancelled": True})

    if order["status"] in ("paid", "fulfilling"):
        # Повторные нажатия не шлём админу — иначе один нетерпеливый клиент
        # завалит чат десятком одинаковых просьб. Клиенту при этом отвечаем
        # так же, как в первый раз: для него ничего не изменилось.
        import time

        now = time.monotonic()
        last = _CANCEL_REQUEST_SENT.get(order["id"], 0)
        if now - last > _CANCEL_REQUEST_COOLDOWN:
            _CANCEL_REQUEST_SENT[order["id"]] = now
            await _request_cancel_from_admin(order, user)
        return web.json_response({"ok": True, "requested": True})

    # completed / rejected — отменять уже нечего
    return web.json_response({"error": "too_late"}, status=400)


async def _request_cancel_from_admin(order: dict, user: dict) -> None:
    """Просьба клиента отменить оплаченный заказ — уходит админу с кнопками."""
    from keyboards.admin_kb import admin_cancel_request_kb

    from services.prices import format_uzs

    who = f"@{user.get('username')}" if user.get("username") else f"id {user['id']}"
    text = (
        f"🙋 Клиент просит отменить оплаченный заказ #{order['id']}.\n"
        f"От: {who}\n"
        f"Товар: {order['item_name']}\n"
        f"Получатель: {order['recipient']}\n"
        f"Сумма: {format_uzs(order['price_uzs'])}\n\n"
        "Если деньги реально не приходили (фейковый чек) — жми «Отменить»."
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await _bot.send_message(
                admin_id,
                text,
                reply_markup=admin_cancel_request_kb(order["id"], order.get("cart_id")),
            )
        except Exception:
            pass


async def handle_submit_receipt(request: web.Request) -> web.Response:
    """
    Приём чека об оплате ПРЯМО ИЗ ВИТРИНЫ (раньше только через чат бота).
    Картинка приходит base64, мы отправляем её админу тем же способом и с
    той же клавиатурой Подтвердить/Отклонить, что и чек из чата — дальше
    весь процесс идёт по уже существующей логике, ничего не дублируем.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _banned_response(user["id"])
    if blocked is not None:
        return blocked

    order_id = _order_id_from(body)
    order = await get_order(order_id)
    # Владелец заказа — иначе по чужому id можно было бы подсунуть чужой чек
    if not order or order["user_id"] != user["id"]:
        print(f"[RECEIPT] not_found: order_id={order_id} user={user['id']}", flush=True)
        return web.json_response({"error": "not_found"}, status=404)
    if order["status"] not in ("awaiting_payment", "payment_review"):
        print(f"[RECEIPT] wrong_status: order={order_id} status={order['status']}", flush=True)
        return web.json_response({"error": "wrong_status"}, status=400)

    image_b64 = body.get("image_base64") or ""
    if not image_b64:
        print(f"[RECEIPT] no_image: order={order_id}", flush=True)
        return web.json_response({"error": "no_image"}, status=400)

    import base64
    from aiogram.types import BufferedInputFile
    from keyboards.admin_kb import admin_review_kb, admin_review_cart_kb
    from services.prices import format_uzs

    try:
        raw = base64.b64decode(image_b64)
    except Exception as e:
        print(f"[RECEIPT] bad_image: order={order_id} err={e}", flush=True)
        return web.json_response({"error": "bad_image"}, status=400)
    if len(raw) > 8 * 1024 * 1024:  # Telegram всё равно не примет больше
        print(f"[RECEIPT] too_big: order={order_id} size={len(raw)}", flush=True)
        return web.json_response({"error": "too_big"}, status=400)

    sender = f"@{user.get('username') or user['id']} (id: {user['id']})"
    cart_id = order.get("cart_id")

    # Отпечаток чека по содержимому картинки: тот же скриншот, приложенный к
    # другому заказу, даст тот же хэш. Из витрины file_unique_id нет, поэтому
    # считаем сами — на дубль это влияет так же.
    import hashlib

    fingerprint = "sha256:" + hashlib.sha256(raw).hexdigest()
    duplicate = await find_order_by_receipt(
        fingerprint, exclude_order_id=order["id"], exclude_cart_id=cart_id
    )
    if duplicate:
        print(
            f"[RECEIPT] дубль: order={order['id']} повторяет #{duplicate['id']}",
            flush=True,
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await _bot.send_message(
                    admin_id,
                    f"🔁 <b>Повторный чек — заблокирован</b>\n\n"
                    f"{sender} приложил в витрине чек, который уже использовали.\n\n"
                    f"Сейчас: заказ #{order['id']} ({order['item_name']})\n"
                    f"Ранее: заказ #{duplicate['id']} ({duplicate['item_name']})\n\n"
                    "Клиенту сказано оплатить заказ отдельно. Делать ничего не нужно.",
                )
            except Exception:
                pass
        return web.json_response({"error": "duplicate_receipt"}, status=409)

    # Второй скриншот того же платежа (экран банка + PDF-квитанция) — обычное
    # дело. Карточку админу показываем, но БЕЗ второй пары кнопок: см.
    # handlers/payment._is_repeat_receipt.
    from handlers.payment import _is_repeat_receipt

    if cart_id:
        # Один чек на всю корзину — одно сообщение админу и одна пара кнопок
        cart_orders = await get_cart_orders(cart_id)
        repeat = _is_repeat_receipt(cart_orders[0] if cart_orders else None)
        total = sum(o["price_uzs"] for o in cart_orders)
        items = "\n".join(f"  • {o['item_name']} → {o['recipient']}" for o in cart_orders)
        caption = (
            f"🛒 <b>Новый чек по корзине {cart_id}</b> ({len(cart_orders)} тов., из мини-аппа)\n"
            f"От: {sender}\n{items}\n"
            f"Итого: {format_uzs(total)}"
            + _expected_line(cart_orders[0] if cart_orders else None)
        )
        markup = None if repeat else admin_review_cart_kb(cart_id)
        if repeat:
            caption = f"🔁 <b>Ещё один чек по корзине {cart_id}</b>\n" + caption.split("\n", 1)[1]
            caption += "\n\n☝️ Кнопки — в первом сообщении по этой корзине."
    else:
        repeat = _is_repeat_receipt(order)
        caption = (
            f"🆕 <b>Новый чек по заказу #{order['id']}</b> (из мини-аппа)\n"
            f"От: {sender}\n"
            f"Товар: {order['item_name']}\n"
            f"Получатель: {order['recipient']}\n"
            f"Сумма: {format_uzs(order['price_uzs'])}"
            + _expected_line(order)
        )
        markup = None if repeat else admin_review_kb(order["id"])
        if repeat:
            caption = (
                f"🔁 <b>Ещё один чек по заказу #{order['id']}</b>\n"
                + caption.split("\n", 1)[1]
                + "\n\n☝️ Кнопки — в первом сообщении по этому заказу."
            )

    sent_any = False
    for admin_id in config.ADMIN_IDS:
        try:
            msg = await _bot.send_photo(
                admin_id,
                BufferedInputFile(raw, filename=f"receipt_{order['id']}.jpg"),
                caption=caption,
                reply_markup=markup,
            )
            if not sent_any and msg.photo:
                # Сохраняем file_id, чтобы чек был виден в карточке заказа,
                # как и при отправке через чат
                if cart_id:
                    await attach_cart_payment_proof(cart_id, msg.photo[-1].file_id)
                    await set_cart_receipt_fingerprint(cart_id, fingerprint)
                else:
                    await attach_payment_proof(order["id"], msg.photo[-1].file_id)
                    await set_receipt_fingerprint(order["id"], fingerprint)
            # Запоминаем сообщение — потом бот сам допишет в него результат
            # автооплаты и «ВЫПОЛНЕНО», чтобы итог был там же, где кнопки.
            if not repeat:
                try:
                    from database.db import remember_admin_card

                    card_ids = [o["id"] for o in cart_orders] if cart_id else [order["id"]]
                    await remember_admin_card(card_ids, admin_id, msg.message_id, caption)
                except Exception:
                    pass
            sent_any = True
        except Exception as e:
            print(f"[RECEIPT] send failed: order={order_id} admin={admin_id} err={e}", flush=True)

    if not sent_any:
        return web.json_response({"error": "send_failed"}, status=500)

    if cart_id:
        await set_cart_status(cart_id, "payment_review")
    else:
        await set_order_status(order["id"], "payment_review")
    return web.json_response({"ok": True})


async def handle_leaderboard(request: web.Request) -> web.Response:
    period = request.query.get("period", "all")
    if period not in PERIOD_TO_SQL:
        return web.json_response({"error": f"unknown period, expected one of {list(PERIOD_TO_SQL)}"}, status=400)

    since_sql = await _period_since_sql(period)
    rows = await get_leaderboard(since_sql, limit=TOP_SIZE)
    pos = await get_leaderboard_position(since_sql, None)
    # Аватарки отдаём только тем, кто сейчас в топе — см. handle_avatar.
    _TOP_USER_IDS.update(r["user_id"] for r in rows)
    return web.json_response({
        "leaderboard": rows, "period": period, "total_people": pos["total_people"],
    })


async def handle_leaderboard_me(request: web.Request) -> web.Response:
    """
    «Где я в рейтинге» за выбранный период — для полоски внизу вкладки TOP.
    Только по подписанной initData: чужое место так не подсмотреть.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)
    user = _extract_verified_user(body)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)
    period = body.get("period", "all")
    if period not in PERIOD_TO_SQL:
        period = "all"
    since_sql = await _period_since_sql(period)
    pos = await get_leaderboard_position(since_sql, user["id"])
    return web.json_response({"ok": True, "top_size": TOP_SIZE, **pos})


# --------------------------------------------------------------------------
# Аватарки для вкладки TOP
# --------------------------------------------------------------------------
# Фото профиля бот может взять у Telegram (getUserProfilePhotos). Но открытый
# эндпоинт «дай фото любого user_id» превратил бы бот в прокси для чужих
# аватарок. Поэтому отдаём фото ТОЛЬКО тем, кто сейчас показан в топе, —
# их имена и так видны всем на этой вкладке.
TOP_SIZE = 8
_TOP_USER_IDS: set = set()
_AVATAR_CACHE: dict = {}          # user_id -> (время, байты | None)
_AVATAR_TTL = 6 * 60 * 60
_AVATAR_CACHE_MAX = 300


async def handle_avatar(request: web.Request) -> web.Response:
    import time
    raw_id = request.match_info.get("user_id", "")
    if not raw_id.isdigit() or len(raw_id) > 20:
        return web.Response(status=404)
    user_id = int(raw_id)
    if user_id not in _TOP_USER_IDS:
        return web.Response(status=404)

    now = time.time()
    cached = _AVATAR_CACHE.get(user_id)
    if cached is None or now - cached[0] > _AVATAR_TTL:
        body = None
        try:
            photos = await _bot.get_user_profile_photos(user_id, limit=1)
            if photos and photos.total_count and photos.photos:
                sizes = photos.photos[0]
                # Самый маленький размер не меньше 160px — хватает на аватарку
                # и не качаем мегабайтное оригинальное фото.
                pick = next((ph for ph in sizes if ph.width >= 160), sizes[-1])
                file = await _bot.get_file(pick.file_id)
                buf = await _bot.download_file(file.file_path)
                body = buf.read()
        except Exception as e:
            logging.info(f"Аватар {user_id} недоступен: {e}")
            body = None
        if len(_AVATAR_CACHE) >= _AVATAR_CACHE_MAX:
            _AVATAR_CACHE.clear()
        # Запоминаем и «фото нет» — иначе без фото дёргали бы Telegram каждый раз.
        cached = (now, body)
        _AVATAR_CACHE[user_id] = cached

    if not cached[1]:
        return web.Response(status=404)
    return web.Response(body=cached[1], content_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=21600"})


# Лимит висящих заказов на клиента живёт в services/order_processing —
# одно число на витрину и на чат, чтобы пути не разъехались.
from services.order_processing import MAX_PENDING_ORDERS_PER_USER


def _expected_line(order) -> str:
    """Строка «ждём ровно N сум» — та же, что в карточке чека из чата."""
    from handlers.payment import _expected_line as line
    return line(dict(order) if order else None)


def _order_id_from(body: dict) -> int:
    """
    order_id из тела запроса — без падения на мусоре.

    Раньше было int(...) напрямую: строка "abc" роняла хендлер с ValueError,
    aiohttp отдавал 500, а витрина показывала клиенту пустую ошибку вместо
    понятного "заказ не найден".
    """
    try:
        return int(body.get("order_id") or 0)
    except (TypeError, ValueError):
        return 0


async def _banned_response(user_id: int) -> web.Response | None:
    """
    Ответ с отказом, если клиент забанен.

    В чате бан ловит middleware, но витрина ходит в API напрямую, минуя
    aiogram — поэтому здесь нужна своя проверка на каждом входе, где клиент
    что-то создаёт или отправляет.
    """
    from database.db import is_banned

    try:
        if not await is_banned(user_id):
            return None
    except Exception:
        return None  # сбой базы не должен закрывать магазин для всех
    print(f"[BAN] отказ забаненному {user_id}", flush=True)
    return web.json_response({"error": "banned"}, status=403)


async def _too_many_pending(user_id: int) -> web.Response | None:
    """Ответ с отказом, если клиент забанен или держит слишком много заказов."""
    blocked = await _banned_response(user_id)
    if blocked is not None:
        return blocked

    pending = await count_pending_orders(user_id)
    if pending < MAX_PENDING_ORDERS_PER_USER:
        return None
    print(f"[ORDER] отказ: у {user_id} уже {pending} незакрытых заказов", flush=True)
    return web.json_response(
        {"error": "too_many_pending", "pending": pending},
        status=429,
    )


async def handle_create_order(request: web.Request) -> web.Response:
    """
    Оформление заказа из мини-аппа В ОБХОД sendData() — нужно для компактной
    Menu Button ("Открыть" у поля ввода), у которой sendData() в принципе не
    работает (ограничение самого Telegram). Подпись initData обязательна —
    иначе кто угодно мог бы оформлять заказы от чужого имени.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _too_many_pending(user["id"])
    if blocked is not None:
        return blocked

    payload = body.get("payload")
    if not isinstance(payload, dict):
        return web.json_response({"error": "missing payload"}, status=400)

    key = StorageKey(bot_id=_bot.id, chat_id=user["id"], user_id=user["id"])
    state = FSMContext(storage=_storage, key=key)

    full_name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()
    try:
        await process_order(
            bot=_bot,
            state=state,
            user_id=user["id"],
            username=user.get("username"),
            full_name=full_name or "Mijoz",
            payload=payload,
        )
    except OrderError as e:
        return web.json_response({"error": str(e)}, status=400)

    return web.json_response({"ok": True})


async def handle_create_cart_order(request: web.Request) -> web.Response:
    """
    Оформление КОРЗИНЫ (несколько товаров — одна оплата) из мини-аппа.
    Как и /public/create_order, требует подписанную initData: без неё можно
    было бы оформлять заказы от чужого имени.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _too_many_pending(user["id"])
    if blocked is not None:
        return blocked

    items = body.get("items")
    key = StorageKey(bot_id=_bot.id, chat_id=user["id"], user_id=user["id"])
    state = FSMContext(storage=_storage, key=key)
    full_name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()

    from services.cart import process_cart_order, CartError

    try:
        result = await process_cart_order(
            bot=_bot,
            state=state,
            user_id=user["id"],
            username=user.get("username"),
            full_name=full_name or "Mijoz",
            items=items,
        )
    except CartError as e:
        return web.json_response({"error": str(e)}, status=400)

    return web.json_response({"ok": True, **result})


async def handle_place_order(request: web.Request) -> web.Response:
    """
    Оформление заказа СРАЗУ, без шага «Всё верно?» в чате: витрина уже
    показала человеку товар, получателя и сумму, и он нажал «Оплатил».
    Возвращает номер заказа и реквизиты — дальше витрина сама показывает
    живой статус (см. /public/order_status).
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _too_many_pending(user["id"])
    if blocked is not None:
        return blocked

    payload = body.get("payload")
    if not isinstance(payload, dict):
        return web.json_response({"error": "missing payload"}, status=400)

    key = StorageKey(bot_id=_bot.id, chat_id=user["id"], user_id=user["id"])
    state = FSMContext(storage=_storage, key=key)
    full_name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()

    from services.order_processing import place_order_direct

    try:
        result = await place_order_direct(
            bot=_bot,
            state=state,
            user_id=user["id"],
            username=user.get("username"),
            full_name=full_name or "Mijoz",
            payload=payload,
        )
    except OrderError as e:
        return web.json_response({"error": str(e)}, status=400)

    return web.json_response({
        "ok": True,
        **result,
        "card_number": config.PAYMENT_CARD_NUMBER,
        "card_holder": config.PAYMENT_CARD_HOLDER,
    })


async def handle_place_cart_order(request: web.Request) -> web.Response:
    """То же самое, но для корзины: несколько товаров — одна сумма к оплате."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    blocked = await _too_many_pending(user["id"])
    if blocked is not None:
        return blocked

    key = StorageKey(bot_id=_bot.id, chat_id=user["id"], user_id=user["id"])
    state = FSMContext(storage=_storage, key=key)
    full_name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()

    from services.cart import place_cart_order_direct, CartError

    try:
        result = await place_cart_order_direct(
            bot=_bot,
            state=state,
            user_id=user["id"],
            username=user.get("username"),
            full_name=full_name or "Mijoz",
            items=body.get("items"),
        )
    except CartError as e:
        return web.json_response({"error": str(e)}, status=400)

    return web.json_response({
        "ok": True,
        **result,
        "card_number": config.PAYMENT_CARD_NUMBER,
        "card_holder": config.PAYMENT_CARD_HOLDER,
    })


async def handle_order_status(request: web.Request) -> web.Response:
    """
    Живой статус конкретного заказа (или всей корзины) — витрина опрашивает
    его раз в несколько секунд, чтобы показывать «проверяем оплату»,
    «выполняется», «готово» прямо в мини-аппе, не отправляя человека в чат.

    Отдаётся ТОЛЬКО владельцу заказа (проверка по подписанной initData).
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    cart_id = (body.get("cart_id") or "").strip()
    order_id = _order_id_from(body)

    orders: list[dict] = []
    if cart_id:
        orders = await get_cart_orders(cart_id)
    elif order_id:
        one = await get_order(order_id)
        orders = [one] if one else []

    if not orders or any(o["user_id"] != user["id"] for o in orders):
        return web.json_response({"error": "not_found"}, status=404)

    main = orders[0]
    total = sum(o["price_uzs"] for o in orders)

    # Статус корзины = самый «ранний» статус среди её товаров: пока хоть один
    # не доделан, вся корзина считается невыполненной.
    STATUS_ORDER = ["rejected", "awaiting_payment", "payment_review", "paid", "fulfilling", "completed"]
    status = min((o["status"] for o in orders), key=lambda s: STATUS_ORDER.index(s) if s in STATUS_ORDER else 99)

    needs_payment = status == "awaiting_payment"
    rent_order = next(
        (o for o in orders
         if o["category"] == "nft_rent" and o["status"] == "paid"
         and not o.get("is_extension") and not (o.get("rent_link") or "")),
        None,
    )

    reviewed = None
    if status == "completed":
        from database.db import get_review
        reviewed = (await get_review(main["id"])) is not None

    return web.json_response({
        "ok": True,
        "order_id": main["id"],
        "cart_id": cart_id or main.get("cart_id"),
        "status": status,
        "reviewed": reviewed,
        "category": main["category"],
        "item_name": main["item_name"],
        "recipient": main["recipient"],
        "price_uzs": total,
        "pay_amount": main.get("expected_amount_uzs") or total,
        "admin_comment": main.get("admin_comment"),
        "is_extension": bool(main.get("is_extension")),
        "needs_payment": needs_payment,
        "needs_rent_link": bool(rent_order),
        "card_number": config.PAYMENT_CARD_NUMBER if needs_payment else None,
        "card_holder": config.PAYMENT_CARD_HOLDER if needs_payment else None,
        "items": [
            {"item_name": o["item_name"], "price_uzs": o["price_uzs"],
             "recipient": o["recipient"], "status": o["status"]}
            for o in orders
        ],
    })


async def handle_my_rentals(request: web.Request) -> web.Response:
    """
    Действующие аренды клиента для раздела «Мои аренды» в мини-аппе:
    что арендовано, сколько осталось и по какой цене можно продлить.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)

    user = validate_init_data(body.get("initData"), config.BOT_TOKEN)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)

    from services.rent_extension import get_active_rentals

    rentals = await get_active_rentals(user["id"])
    return web.json_response({"rentals": rentals})


async def handle_diag(request: web.Request) -> web.Response:
    """
    Временный эндпоинт для отладки бага с Tarix/Profil (пустой initData на
    некоторых телефонах). Ничего не сохраняет в базу — просто печатает в
    лог процесса (виден в Railway → Logs). Можно удалить, когда баг найдём.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    print(f"[DIAG] {body}", flush=True)
    return web.json_response({"ok": True})


# --------------------------------------------------------------------------
# Анимированные (премиальные) эмодзи Telegram в витрине
# --------------------------------------------------------------------------
# В Telegram премиальный эмодзи — это не символ, а id вроде 5375583215157280942.
# В сообщении бот умеет его показать (<tg-emoji emoji-id=...>), а мини-апп —
# обычная веб-страница: браузер про такой id ничего не знает и покажет пустоту.
#
# Зато у бота есть доступ к самому файлу эмодзи: getCustomEmojiStickers отдаёт
# по id стикер, а его уже можно скачать и раздать витрине как обычный файл.
# Именно это здесь и происходит.
#
# Файл весит килобайты и никогда не меняется, поэтому держим копию в памяти и
# отдаём с длинным Cache-Control: у Telegram качаем один раз за перезапуск.
_EMOJI_CACHE: dict = {}


async def handle_custom_emoji(request: web.Request) -> web.Response:
    emoji_id = request.match_info.get("emoji_id", "")
    # Только цифры: id уходит в запрос к Telegram, и пускать туда произвольную
    # строку из интернета незачем.
    if not emoji_id.isdigit() or len(emoji_id) > 24:
        return web.Response(status=404, text="bad emoji id")

    cached = _EMOJI_CACHE.get(emoji_id)
    if cached is None:
        try:
            stickers = await _bot.get_custom_emoji_stickers([emoji_id])
        except Exception as e:
            logging.warning(f"Не удалось получить эмодзи {emoji_id}: {e}")
            return web.Response(status=404, text="not found")
        if not stickers:
            return web.Response(status=404, text="not found")
        sticker = stickers[0]
        try:
            file = await _bot.get_file(sticker.file_id)
            buf = await _bot.download_file(file.file_path)
            raw = buf.read()
        except Exception as e:
            logging.warning(f"Не удалось скачать эмодзи {emoji_id}: {e}")
            return web.Response(status=404, text="download failed")

        if getattr(sticker, "is_animated", False):
            # .tgs — это gzip поверх Lottie-JSON. Распаковываем здесь, чтобы
            # витрине не тащить ещё и распаковщик в браузер.
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
            ctype = "application/json"
        elif getattr(sticker, "is_video", False):
            ctype = "video/webm"
        else:
            ctype = "image/webp"
        cached = (raw, ctype)
        _EMOJI_CACHE[emoji_id] = cached

    body, ctype = cached
    # Тип витрина определяет по Content-Type ответа — отдельного запроса за
    # "а что это за файл" не нужно.
    return web.Response(
        body=body,
        content_type=ctype,
        headers={"Cache-Control": "public, max-age=604800"},
    )


# --------------------------------------------------------------------------
# «Я в спаме» — клиент не может написать админу первым
# --------------------------------------------------------------------------
# Premium владелец оформляет руками, поэтому после оплаты витрина предлагает
# написать ему. Но аккаунт в спам-блоке Telegram не может первым написать
# незнакомому человеку. Тогда клиент жмёт «Men spamdaman», а бот присылает
# владельцу уведомление. Ответ на это уведомление (Reply) бот доставит
# клиенту сам — боту клиент писал, поэтому ему бот написать может всегда.
_SPAM_HELP_SENT: dict[int, float] = {}
_SPAM_HELP_COOLDOWN = 10 * 60

_SPAM_HELP_REPLY = {
    "uz": "✅ Adminga xabar berildi — u sizga shu bot orqali yozadi.",
    "ru": "✅ Админ уведомлён — он напишет вам через этого бота.",
    "en": "✅ The admin has been notified — they'll message you through this bot.",
}


async def handle_spam_help(request: web.Request) -> web.Response:
    import html as _html
    import time
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)
    user = _extract_verified_user(body)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)
    blocked = await _banned_response(user["id"])
    if blocked is not None:
        return blocked

    order = await get_order(_order_id_from(body))
    if not order or order["user_id"] != user["id"] or order["status"] not in ("paid", "fulfilling", "completed"):
        return web.json_response({"error": "not_found"}, status=404)

    now = time.monotonic()
    if now - _SPAM_HELP_SENT.get(order["id"], 0.0) < _SPAM_HELP_COOLDOWN:
        return web.json_response({"ok": True, "repeat": True})  # уже сообщили — не спамим админа
    _SPAM_HELP_SENT[order["id"]] = now

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from database.db import get_user_language, save_support_mapping

    name = _html.escape(" ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or "—")
    uname = f"@{_html.escape(user['username'])}" if user.get("username") else "без username"
    text = (
        "🚫 <b>Клиент в спам-блоке</b> — сам написать тебе не может.\n\n"
        f"Заказ #{order['id']} · {_html.escape(order['item_name'] or '')}\n"
        f"Клиент: {name} · {uname} · <code>{user['id']}</code>\n\n"
        "👉 <b>Ответь на это сообщение</b> (Reply) — бот перешлёт ответ клиенту."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Открыть профиль клиента", url=f"tg://user?id={user['id']}")
    ]])
    for admin_id in config.ADMIN_IDS:
        try:
            msg = await _bot.send_message(admin_id, text, reply_markup=kb)
            await save_support_mapping(admin_id, msg.message_id, user["id"])
        except Exception:
            pass

    lang = await get_user_language(user["id"]) or "uz"
    try:
        await _bot.send_message(user["id"], _SPAM_HELP_REPLY.get(lang, _SPAM_HELP_REPLY["uz"]))
    except Exception:
        pass
    return web.json_response({"ok": True})


# --------------------------------------------------------------------------
# Отзывы
# --------------------------------------------------------------------------
_REVIEWS_CACHE: dict = {"at": 0.0, "data": None}


async def handle_submit_review(request: web.Request) -> web.Response:
    """Оценка из витрины (экран «Bajarildi»). Общая логика — services/reviews.py."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad request body"}, status=400)
    user = _extract_verified_user(body)
    if not user:
        return web.json_response({"error": "invalid or expired initData"}, status=403)
    blocked = await _banned_response(user["id"])
    if blocked is not None:
        return blocked

    from services.reviews import submit_review
    result, _ = await submit_review(_bot, _order_id_from(body), user["id"],
                                    body.get("rating"), body.get("comment"))
    if result != "ok":
        return web.json_response({"ok": False, "error": result}, status=400)
    _REVIEWS_CACHE["at"] = 0.0  # новый отзыв сразу виден в ленте
    return web.json_response({"ok": True})


async def handle_reviews(request: web.Request) -> web.Response:
    """Средняя оценка и свежие отзывы для витрины. Кэш на минуту."""
    import time
    from database.db import get_reviews_summary
    now = time.time()
    if _REVIEWS_CACHE["data"] is None or now - _REVIEWS_CACHE["at"] > 60:
        _REVIEWS_CACHE["data"] = await get_reviews_summary(limit=30)
        _REVIEWS_CACHE["at"] = now
    return web.json_response(_REVIEWS_CACHE["data"])


async def handle_preflight(request: web.Request) -> web.Response:
    return web.Response(status=204)


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Internal-Secret"
    return response


async def start_stats_server(bot, storage):
    """Запускается фоновой задачей рядом с polling бота (см. bot.py).
    bot и storage нужны для /public/create_order — тот же Storage, что
    использует Dispatcher, иначе дальнейшее подтверждение заказа кнопками
    в чате не увидит созданный черновик."""
    global _bot, _storage
    _bot, _storage = bot, storage

    # БАГ БЫЛ ЗДЕСЬ: у aiohttp лимит тела запроса по умолчанию 1 МБ, а чек с
    # телефона в base64 весит 3-6 МБ. Запрос обрывался ДО наших проверок, и
    # клиент видел непонятное "bad request body" — причём у одного проходило
    # (мелкий скриншот), а у другого нет. Витрина теперь ещё и сжимает фото
    # перед отправкой, но запас на сервере всё равно нужен.
    app = web.Application(middlewares=[cors_middleware], client_max_size=20 * 1024 * 1024)
    app.router.add_get("/internal/stats", handle_stats)
    app.router.add_post("/public/my_orders", handle_my_orders)
    app.router.add_post("/public/my_stats", handle_my_stats)
    app.router.add_get("/public/leaderboard", handle_leaderboard)
    app.router.add_post("/public/review", handle_submit_review)
    app.router.add_post("/public/spam_help", handle_spam_help)
    app.router.add_get("/public/reviews", handle_reviews)
    app.router.add_post("/public/leaderboard_me", handle_leaderboard_me)
    app.router.add_get("/public/avatar/{user_id}", handle_avatar)
    app.router.add_get("/public/emoji/{emoji_id}", handle_custom_emoji)
    app.router.add_post("/public/_diag", handle_diag)
    app.router.add_post("/public/create_order", handle_create_order)
    app.router.add_post("/public/create_cart_order", handle_create_cart_order)
    app.router.add_post("/public/place_order", handle_place_order)
    app.router.add_post("/public/place_cart_order", handle_place_cart_order)
    app.router.add_post("/public/order_status", handle_order_status)
    app.router.add_post("/public/my_rentals", handle_my_rentals)
    app.router.add_post("/public/active_order", handle_active_order)
    app.router.add_post("/public/submit_rent_link", handle_submit_rent_link)
    app.router.add_post("/public/send_rent_tutorial", handle_send_rent_tutorial)
    app.router.add_post("/public/send_display_video", handle_send_display_video)
    app.router.add_post("/public/balance", handle_balance)
    app.router.add_post("/public/create_topup", handle_create_topup)
    app.router.add_post("/public/pay_from_balance", handle_pay_from_balance)
    app.router.add_post("/public/cancel_topup", handle_cancel_topup)
    app.router.add_post("/public/topup_receipt", handle_topup_receipt)
    app.router.add_post("/public/cancel_order", handle_cancel_order)
    app.router.add_post("/public/submit_receipt", handle_submit_receipt)
    for path in ("/public/my_orders", "/public/my_stats", "/public/leaderboard_me", "/public/review", "/public/spam_help", "/public/_diag", "/public/create_order",
                 "/public/create_cart_order", "/public/my_rentals",
                 "/public/place_order", "/public/place_cart_order", "/public/order_status",
                 "/public/active_order", "/public/submit_rent_link", "/public/cancel_order", "/public/submit_receipt"):
        app.router.add_route("OPTIONS", path, handle_preflight)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.STATS_API_PORT)
    await site.start()
