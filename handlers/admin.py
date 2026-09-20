from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import base64
import io

import httpx

import config
from database.db import (
    get_order, set_order_status, get_stats, get_all_user_ids,
    get_cart_orders, set_cart_status,
)
from keyboards.admin_kb import admin_fulfill_kb, admin_cancel_kb
from services.prices import format_uzs
from services.fragment_service import try_auto_fulfill_stars, notify_manual_premium
from services.marketapp_service import start_rent_payment
from services.rent_link import send_rent_link_tutorial
from services.telegram_gifts import fulfill_simple_gift
from services.public_channel import post_completed_order
from services.live_feed import push_live_feed_event

FEED_EMOJI = {"stars": "⭐", "premium": "💎", "simple_gift": "🎁", "nft_rent": "🖼"}
from services.i18n import t
from database.db import get_user_language as _get_user_language

router = Router()


class BroadcastStates(StatesGroup):
    waiting_message = State()


class AddGiftStates(StatesGroup):
    waiting_gift_id = State()
    waiting_star_count = State()
    waiting_price = State()
    waiting_sticker = State()


class GetFileIdStates(StatesGroup):
    waiting_file = State()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.message(Command("getfileid"))
async def get_file_id_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(GetFileIdStates.waiting_file)
    await message.answer(
        "📎 Пришли (или перешли) сюда видео с туром аренды — отвечу его file_id.\n"
        "Его нужно один раз вписать в переменную RENT_TUTORIAL_VIDEO на Railway "
        "(сервис Worker) и перезапустить бота."
    )


@router.message(GetFileIdStates.waiting_file, Command("cancel"))
async def get_file_id_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.")


@router.message(GetFileIdStates.waiting_file, F.video)
async def get_file_id_video(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✅ file_id этого видео:\n<code>" + message.video.file_id + "</code>\n\n"
        "Скопируй и вставь как значение переменной <code>RENT_TUTORIAL_VIDEO</code> "
        "на Railway (сервис Worker) → Variables → перезапусти сервис."
    )


@router.message(GetFileIdStates.waiting_file)
async def get_file_id_wrong_type(message: Message):
    await message.answer("Это не видео. Пришли именно видеофайл (или /cancel).")


@router.message(Command("chatid"))
async def chat_id_cmd(message: Message):
    """
    Показывает ID ТЕКУЩЕГО чата. Нужен при настройке автопроверки оплаты:
    добавляешь бота в группу, куда пересылаются SMS от банка, пишешь там
    /chatid — и вписываешь полученное число в переменную SMS_RELAY_CHAT_ID
    на Railway. У групп ID отрицательный (например -1001234567890) — это нормально.
    """
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        f"🆔 ID этого чата: <code>{message.chat.id}</code>\n"
        f"Тип: {message.chat.type}\n\n"
        "Для автопроверки оплаты по SMS впиши это число в переменную "
        "<code>SMS_RELAY_CHAT_ID</code> (Railway → сервис Worker → Variables)."
    )


@router.message(Command("cleargifts"))
async def clear_gifts_cmd(message: Message):
    """Убирает ВСЕ вручную добавленные подарки. Нужна отдельная команда,
    потому что список живёт на персистентном Volume веб-сервиса — правка
    файла в репозитории и редеплой его не затирают."""
    if not is_admin(message.from_user.id):
        return
    if not config.WEBAPP_URL or not config.INTERNAL_PUSH_SECRET:
        await message.answer("⚠️ Не настроен WEBAPP_URL или INTERNAL_PUSH_SECRET.")
        return
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{config.WEBAPP_URL}/internal/clear_gifts",
                headers={"X-Internal-Secret": config.INTERNAL_PUSH_SECRET},
            )
        if r.status_code == 200:
            await message.answer("✅ Вручную добавленные подарки удалены из каталога.")
        else:
            await message.answer(f"⚠️ Веб-сервис ответил {r.status_code}: {r.text}")
    except Exception as e:
        await message.answer(f"⚠️ Не удалось связаться с веб-сервисом: {e}")


@router.message(Command("addgift"))
async def add_gift_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        # Раньше здесь был просто return — бот молчал в ответ, и было
        # невозможно понять, то ли команда сломана, то ли твой Telegram ID
        # просто не совпадает с тем, что прописан в ADMIN_IDS на Railway.
        await message.answer(
            f"⛔ Команда только для админа.\nТвой ID: {message.from_user.id}\n"
            "Если это ты — добавь этот ID в переменную ADMIN_IDS сервиса Worker на Railway "
            "(через запятую, если админов несколько) и перезапусти сервис."
        )
        return
    await state.set_state(AddGiftStates.waiting_gift_id)
    await message.answer(
        "➕ Добавляем снятый с продажи подарок в каталог.\n\n"
        "1) Пришли gift_id — длинное число (пример: 6046178578163303744)."
    )


@router.message(AddGiftStates.waiting_gift_id)
async def add_gift_id(message: Message, state: FSMContext):
    gift_id = message.text.strip()
    if not gift_id.isdigit():
        await message.answer("Нужно просто число, без пробелов и лишних символов. Попробуй ещё раз:")
        return
    await state.update_data(gift_id=gift_id)
    await state.set_state(AddGiftStates.waiting_star_count)
    await message.answer("2) Сколько звёзд этот подарок реально стоит в Telegram? (нужно, чтобы бот смог его подарить). Например: 50")


@router.message(AddGiftStates.waiting_star_count)
async def add_gift_stars(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Нужно число. Например: 50")
        return
    await state.update_data(star_count=int(text))
    await state.set_state(AddGiftStates.waiting_price)
    await message.answer("3) За сколько сум продавать в магазине? Например: 15000")


@router.message(AddGiftStates.waiting_price)
async def add_gift_price(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Нужно число. Например: 15000")
        return
    await state.update_data(price_uzs=int(text))
    await state.set_state(AddGiftStates.waiting_sticker)
    await message.answer(
        "4) Теперь пришли сам стикер этого подарка (если он есть в наборе стикеров или "
        "ты можешь его как-то отправить как обычный стикер) — я возьму из него картинку.\n\n"
        "Если стикера под рукой нет — напиши /skip, сохраню без картинки (в магазине будет эмодзи)."
    )


async def _push_gift_to_web(data: dict, sticker_bytes: bytes | None, ext: str | None) -> str:
    """Отправляет данные подарка (и картинку, если есть) на сервис oson-store-web,
    где физически лежит статика магазина. Возвращает текст для ответа админу."""
    if not config.WEBAPP_URL or not config.INTERNAL_PUSH_SECRET:
        return "⚠️ Не настроен WEBAPP_URL или INTERNAL_PUSH_SECRET — не могу передать подарок на веб-сервис."

    payload = {
        "gift_id": data["gift_id"],
        "star_count": data["star_count"],
        "price_uzs": data["price_uzs"],
        "sticker_emoji": "🎁",
    }
    if sticker_bytes:
        payload["image_base64"] = base64.b64encode(sticker_bytes).decode()
        payload["image_ext"] = ext

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{config.WEBAPP_URL}/internal/add_gift",
                json=payload,
                headers={"X-Internal-Secret": config.INTERNAL_PUSH_SECRET},
            )
        if r.status_code != 200:
            return f"⚠️ Веб-сервис ответил ошибкой {r.status_code}: {r.text}"
    except httpx.RequestError as e:
        return f"⚠️ Не удалось достучаться до веб-сервиса: {e}"

    has_image = bool(sticker_bytes)
    return f"✅ Подарок #{data['gift_id']} добавлен в каталог" + (" с картинкой!" if has_image else " (без картинки, будет эмодзи 🎁).")


@router.message(AddGiftStates.waiting_sticker, F.sticker)
async def add_gift_sticker(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    sticker = message.sticker

    # Берём статичное превью (thumbnail) — оно почти всегда JPEG/WebP и точно
    # откроется как обычная картинка в браузере. Сам файл стикера может быть
    # анимацией (.tgs) или видео (.webm), которые для <img> не подходят.
    file_id, ext = None, None
    if sticker.thumbnail:
        file_id, ext = sticker.thumbnail.file_id, "jpg"
    elif not sticker.is_animated and not sticker.is_video:
        file_id, ext = sticker.file_id, "webp"

    sticker_bytes = None
    if file_id:
        buf = io.BytesIO()
        await bot.download(file_id, destination=buf)
        sticker_bytes = buf.getvalue()

    reply = await _push_gift_to_web(data, sticker_bytes, ext)
    await state.clear()
    await message.answer(reply)


@router.message(
    AddGiftStates.waiting_sticker,
    F.entities.func(lambda entities: any(e.type == "custom_emoji" for e in (entities or []))),
)
async def add_gift_custom_emoji(message: Message, state: FSMContext, bot: Bot):
    """
    Premium-юзеры часто шлют не обычный стикер, а custom emoji прямо в тексте
    (доступно только с Telegram Premium) — у такого сообщения message.sticker
    пустой, это текст с entity типа custom_emoji, поэтому предыдущий хендлер
    его не ловит. Тут достаём реальный стикер за custom_emoji_id через API и
    обрабатываем точно так же, как обычный присланный стикер.
    """
    data = await state.get_data()
    custom_emoji_id = next(e.custom_emoji_id for e in message.entities if e.type == "custom_emoji")

    stickers = await bot.get_custom_emoji_stickers(custom_emoji_ids=[custom_emoji_id])
    if not stickers:
        await message.answer(
            "Не удалось получить картинку из этого эмодзи. Пришли обычный стикер или /skip."
        )
        return
    sticker = stickers[0]

    file_id, ext = None, None
    if sticker.thumbnail:
        file_id, ext = sticker.thumbnail.file_id, "jpg"
    elif not sticker.is_animated and not sticker.is_video:
        file_id, ext = sticker.file_id, "webp"

    sticker_bytes = None
    if file_id:
        buf = io.BytesIO()
        await bot.download(file_id, destination=buf)
        sticker_bytes = buf.getvalue()

    reply = await _push_gift_to_web(data, sticker_bytes, ext)
    await state.clear()
    await message.answer(reply)


@router.message(AddGiftStates.waiting_sticker, Command("skip"))
async def add_gift_skip(message: Message, state: FSMContext):
    data = await state.get_data()
    reply = await _push_gift_to_web(data, None, None)
    await state.clear()
    await message.answer(reply)


@router.message(Command("admin"))
async def admin_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🛠 Админ-команды:\n"
        "/stats — статистика по пользователям и заказам\n"
        "/broadcast — разослать сообщение всем пользователям\n"
        "/order_&lt;id&gt; — посмотреть заказ (напр. /order_5)\n"
        "/cancel &lt;id&gt; — отменить заказ на любом этапе, даже уже оплаченный "
        "(напр. /cancel 19) — снимает его у клиента из витрины\n"
        "/tonwallet — кошелёк магазина: адрес, баланс, лимиты и последние "
        "автоплатежи (проверь ПЕРЕД включением автооплаты)\n"
        "/addgift — добавить снятый с продажи Telegram-подарок в каталог (с картинкой)\n"
        "/getfileid — получить file_id видео (для RENT_TUTORIAL_VIDEO)\n"
        "/myid — узнать свой Telegram ID (сверить с ADMIN_IDS)\n"
        "/chatid — ID текущего чата (нужен для SMS_RELAY_CHAT_ID)\n"
        "/topup &lt;кол-во⭐&gt; — пополнить баланс звёзд САМОГО БОТА (нужно, чтобы sendGift "
        "мог реально дарить подарки — см. /topup без аргумента для подробностей)\n\n"
        "Подтверждение/отклонение оплаты — кнопками под чеком."
    )


@router.message(Command("topup"))
async def topup_stars(message: Message, command):
    """
    Пополнение баланса Stars САМОГО БОТА (не пользователя) — это единственный
    официальный способ дать боту звёзды, чтобы sendGift (простые подарки)
    вообще мог работать: бот дарит подарки С СОБСТВЕННОГО баланса звёзд, а
    этот баланс пополняется только реальными Stars-платежами В БОТА.

    Команда выставляет обычный Telegram-инвойс в звёздах (валюта XTR) на
    указанную сумму. Админ оплачивает его сам своими Stars — после оплаты
    вся сумма зачисляется на баланс бота (Telegram не берёт комиссию с
    оплаты внутри бота), после чего sendGift сможет списывать с этого
    баланса при отправке простых подарков.
    """
    if not is_admin(message.from_user.id):
        return

    args = (command.args or "").strip()
    if not args.isdigit() or int(args) <= 0:
        await message.answer(
            "Использование: <code>/topup 500</code> — выставит счёт на 500⭐.\n\n"
            "Как это работает: ты сам оплачиваешь этот счёт своими Telegram Stars, "
            "и вся сумма зачисляется на баланс БОТА (не тебе). Это единственный способ "
            "дать боту звёзды, чтобы /addgift и sendGift (простые подарки) реально "
            "могли отправляться клиентам — иначе будет BALANCE_TOO_LOW.\n\n"
            "Если своих звёзд не хватает — сначала купи их себе: Telegram → Settings → "
            "Stars → Buy Stars."
        )
        return

    stars = int(args)
    await message.answer_invoice(
        title=f"Пополнение баланса бота на {stars}⭐",
        description=(
            f"Оплати сам — эти {stars}⭐ зачислятся на баланс бота, "
            "чтобы он мог отправлять подарки клиентам через sendGift."
        ),
        payload=f"bot_stars_topup:{stars}",
        provider_token="",  # для Stars (XTR) провайдер не нужен
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
    )


@router.pre_checkout_query()
async def topup_pre_checkout(pre_checkout_q):
    # Единственный платёж в этом боте, идущий через сам Telegram, — пополнение
    # баланса бота звёздами (см. /topup). Подтверждаем всегда: сумма и валюта
    # уже зафиксированы в инвойсе выше, подделать их на этом шаге нельзя.
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def topup_success(message: Message):
    payload = message.successful_payment.invoice_payload
    stars = message.successful_payment.total_amount
    if payload.startswith("bot_stars_topup:"):
        await message.answer(
            f"✅ Баланс бота пополнен на {stars}⭐. Теперь /addgift и обычные подарки "
            "должны отправляться без ошибки BALANCE_TOO_LOW."
        )


@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastStates.waiting_message)
    await message.answer(
        "✍️ Пришли сообщение (текст, фото, видео — что угодно), которое разослать "
        "ВСЕМ пользователям бота. Для отмены — /cancel"
    )


@router.message(BroadcastStates.waiting_message, Command("cancel"))
async def broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Рассылка отменена.")


@router.message(BroadcastStates.waiting_message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_ids = await get_all_user_ids()

    status_msg = await message.answer(f"⏳ Рассылаю {len(user_ids)} пользователям...")
    sent, failed = 0, 0

    for user_id in user_ids:
        try:
            await bot.copy_message(user_id, message.chat.id, message.message_id)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # не упереться в лимиты Telegram на массовую отправку

    await status_msg.edit_text(f"✅ Разослано: {sent}\n❌ Не доставлено: {failed}")


@router.message(Command("stats"))
async def stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    s = await get_stats()
    status_labels = {
        "awaiting_payment": "Ожидают оплаты",
        "payment_review": "На проверке",
        "paid": "Оплачены",
        "fulfilling": "Выполняются",
        "completed": "Выполнены",
        "rejected": "Отклонены",
    }
    status_lines = "\n".join(
        f"  • {status_labels.get(k, k)}: {v}" for k, v in s["orders_by_status"].items()
    ) or "  —"

    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{s['total_users']}</b>\n"
        f"🟢 Активных за 24ч: <b>{s['active_24h']}</b>\n"
        f"🟢 Активных за 7дн: <b>{s['active_7d']}</b>\n\n"
        f"📦 Всего заказов: <b>{s['total_orders']}</b>\n"
        f"{status_lines}"
    )


async def _send_attached_content(bot: Bot, order_id: int, order: dict) -> None:
    """Видео/текст-инструкция, если админ прикрепил их к заказу."""
    if order.get("content_video_url"):
        try:
            await bot.send_video(
                order["user_id"],
                order["content_video_url"],
                caption="📹 Вот видео-инструкция как использовать ваш заказ!",
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Ошибка при отправке видео для заказа {order_id}: {e}")

    if order.get("content_text"):
        try:
            await bot.send_message(
                order["user_id"],
                f"📖 <b>Инструкция:</b>\n{order['content_text']}",
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Ошибка при отправке текста для заказа {order_id}: {e}")


async def _fulfill_order(bot: Bot, order_id: int, order: dict) -> None:
    """
    Само выполнение заказа по его категории. Вынесено отдельно, потому что
    вызывается из двух мест: обычный заказ (finalize_payment) и каждый товар
    оплаченной корзины (finalize_cart_payment) — логика выполнения у них
    одна и та же, отличается только то, что вокруг (сообщения клиенту).
    """
    if order["category"] == "stars":
        await try_auto_fulfill_stars(bot, order)

    elif order["category"] == "premium":
        await notify_manual_premium(bot, order)

    elif order["category"] == "nft_rent":
        await start_rent_payment(
            bot, order, order["nft_address"], float(order["base_price_per_day_gram"]), order["rent_days"]
        )
        if order.get("is_extension"):
            # Продление: гифт уже подключён к профилю клиента, повторная
            # tc://-ссылка не нужна — иначе человек получит непонятную
            # инструкцию "подключите подарок", хотя он у него уже есть.
            lang = await _get_user_language(order["user_id"])
            await bot.send_message(
                order["user_id"],
                t(lang, "rent_extended").format(
                    item_name=order["item_name"], days=order["rent_days"]
                ),
            )
        else:
            await send_rent_link_tutorial(bot, order)
            if not config.RENT_TUTORIAL_VIDEO:
                for admin_id in config.ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            "⚠️ RENT_TUTORIAL_VIDEO не настроен — клиенту ушёл только текст, "
                            "без видео. Отправь мне видео через /getfileid, чтобы это исправить.",
                        )
                    except Exception:
                        pass

    elif order["category"] == "simple_gift":
        success, note = await fulfill_simple_gift(bot, order)
        if success:
            await set_order_status(order_id, "completed")
            lang = await _get_user_language(order["user_id"])
            await bot.send_message(
                order["user_id"],
                t(lang, "order_completed").format(order_id=order_id, item_name=order["item_name"]),
            )
            await post_completed_order(bot, order)
            await push_live_feed_event(FEED_EMOJI.get("simple_gift", "🎁"), order["item_name"])
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"Заказ #{order_id}: {note}")
            except Exception:
                pass


async def finalize_payment(bot: Bot, order_id: int, order: dict) -> None:
    """
    Всё, что должно произойти, когда оплата заказа подтверждена — неважно,
    админ нажал «✅ Подтверждено» вручную или это подтвердилось автоматически
    (по совпадению уникальной суммы с SMS о поступлении на карту).
    """
    await set_order_status(order_id, "paid")

    lang = await _get_user_language(order["user_id"])
    await bot.send_message(
        order["user_id"],
        t(lang, "payment_confirmed").format(order_id=order_id),
    )

    await _send_attached_content(bot, order_id, order)

    # Мягкая допродажа смежной категории (купил Stars -> предлагаем Premium и т.д.)
    try:
        from services.upsell import send_upsell
        await send_upsell(bot, order["user_id"], order["category"], lang)
    except Exception:
        pass  # апсейл не критичен — не мешаем основному потоку оплаты

    await _fulfill_order(bot, order_id, order)


async def finalize_cart_payment(bot: Bot, cart_id: str, cart_orders: list[dict] | None = None) -> None:
    """
    Подтверждение оплаты КОРЗИНЫ: товаров несколько, но деньги пришли одни —
    поэтому клиенту уходит ОДНО сообщение и ОДИН апсейл, а выполняется каждый
    товар отдельно, своей обычной логикой.
    """
    orders = cart_orders if cart_orders is not None else await get_cart_orders(cart_id)
    if not orders:
        return

    await set_cart_status(cart_id, "paid")

    user_id = orders[0]["user_id"]
    lang = await _get_user_language(user_id)
    items = "\n".join(f"  • {o['item_name']} → {o['recipient']}" for o in orders)
    try:
        await bot.send_message(
            user_id,
            t(lang, "cart_payment_confirmed").format(count=len(orders)) + f"\n{items}",
        )
    except Exception:
        pass

    # Апсейл — один на всю корзину, по самому дорогому товару в ней
    # (иначе после корзины из пяти позиций человек получил бы пять реклам).
    try:
        from services.upsell import send_upsell
        top = max(orders, key=lambda o: o["price_uzs"])
        await send_upsell(bot, user_id, top["category"], lang)
    except Exception:
        pass

    for o in orders:
        o = dict(o, status="paid")
        await _send_attached_content(bot, o["id"], o)
        try:
            await _fulfill_order(bot, o["id"], o)
        except Exception as e:
            print(f"[cart {cart_id}] ошибка выполнения заказа #{o['id']}: {e}", flush=True)
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"⚠️ Корзина {cart_id}: заказ #{o['id']} ({o['item_name']}) "
                        f"не выполнился автоматически: {e}. Выполни вручную.",
                    )
                except Exception:
                    pass


@router.callback_query(F.data.startswith("admin:approve:"))
async def approve_payment(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await call.message.edit_caption(
        caption=(call.message.caption or "") + "\n\n✅ Оплата подтверждена",
        reply_markup=admin_fulfill_kb(order_id),
    )
    await call.answer("Подтверждено")

    await finalize_payment(bot, order_id, order)


@router.callback_query(F.data.startswith("admin:reject:"))
async def reject_payment(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await set_order_status(order_id, "rejected", admin_comment="Оплата не подтверждена")
    await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ Отклонено")
    await call.answer("Отклонено")

    lang = await _get_user_language(order["user_id"])
    await bot.send_message(
        order["user_id"],
        t(lang, "order_rejected").format(order_id=order_id),
    )


@router.callback_query(F.data.startswith("admin:approve_cart:"))
async def approve_cart_payment(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    cart_id = call.data.split(":", 2)[2]
    orders = await get_cart_orders(cart_id)
    if not orders:
        await call.answer("Корзина не найдена", show_alert=True)
        return

    # Кнопки "Заказ выполнен" — по одной на товар: выполняются они всё-таки
    # по отдельности (звёзды через кошелёк, премиум вручную и т.д.).
    b = InlineKeyboardBuilder()
    for o in orders:
        b.button(text=f"📤 Выполнен: {o['item_name'][:28]}", callback_data=f"admin:done:{o['id']}")
    b.adjust(1)

    await call.message.edit_caption(
        caption=(call.message.caption or "") + "\n\n✅ Оплата подтверждена (вся корзина)",
        reply_markup=b.as_markup(),
    )
    await call.answer("Подтверждено")

    await finalize_cart_payment(bot, cart_id, orders)


@router.callback_query(F.data.startswith("admin:reject_cart:"))
async def reject_cart_payment(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    cart_id = call.data.split(":", 2)[2]
    orders = await get_cart_orders(cart_id)
    if not orders:
        await call.answer("Корзина не найдена", show_alert=True)
        return

    await set_cart_status(cart_id, "rejected", "Оплата не подтверждена")
    await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ Отклонено (вся корзина)")
    await call.answer("Отклонено")

    lang = await _get_user_language(orders[0]["user_id"])
    try:
        await bot.send_message(orders[0]["user_id"], t(lang, "cart_rejected"))
    except Exception:
        pass


@router.message(Command("tonwallet"))
async def ton_wallet_cmd(message: Message):
    """
    Проверка кошелька ДО включения автоплатежа.

    Главное, что здесь видно, — какой адрес получается из сид-фразы. У одной
    и той же фразы версии V5R1 и V4R2 дают РАЗНЫЕ адреса, и деньги лежат
    только на одном. Поэтому показываем оба с балансами: тот, где баланс и
    который совпадает с кошельком из marketapp.org, и надо указать в
    TON_WALLET_VERSION. Команда ничего не отправляет и не подписывает.
    """
    if not is_admin(message.from_user.id):
        return

    from database.db import get_ton_payments, get_ton_spent_today_nano
    from services import ton_wallet

    lines = ["🔑 <b>TON-кошелёк магазина</b>\n"]
    lines.append(f"Автоплатёж: {'✅ включён' if config.TON_AUTO_PAY_ENABLED else '❌ выключен'}")
    lines.append(f"Сид-фраза: {'задана' if config.TON_WALLET_MNEMONIC else '❌ НЕ задана'}")
    lines.append(f"Версия в настройках: <code>{config.TON_WALLET_VERSION}</code>")
    lines.append(
        f"Лимиты: {config.TON_AUTO_PAY_MAX_TON} TON за раз, "
        f"{config.TON_AUTO_PAY_DAILY_MAX_TON} TON в сутки"
    )

    if config.TON_WALLET_MNEMONIC:
        lines.append("\n<b>Адреса из твоей сид-фразы:</b>")
        for version in ("v5r1", "v4r2"):
            try:
                info = await ton_wallet.get_wallet_info(version)
                bal = info.get("balance_ton")
                bal_text = f"{bal:.4f} TON" if isinstance(bal, (int, float)) else "баланс не получен"
                lines.append(f"\n<b>{version}</b>\n<code>{info['address']}</code>\n{bal_text}")
            except Exception as e:
                lines.append(f"\n<b>{version}</b> — ошибка: {e}")
        lines.append(
            "\n\n👆 Укажи в <code>TON_WALLET_VERSION</code> ту версию, чей адрес "
            "совпадает с кошельком, которым ты генерировал токен на marketapp.org."
        )

    spent = await get_ton_spent_today_nano()
    lines.append(f"\n\n💸 Потрачено сегодня: {spent / 1_000_000_000:.4f} TON")

    payments = await get_ton_payments(5)
    if payments:
        lines.append("\n<b>Последние автоплатежи:</b>")
        icon = {"sent": "✅", "failed": "❌", "sending": "⏳"}
        for p in payments:
            lines.append(
                f"{icon.get(p['status'], '•')} #{p['order_id']} {p['purpose']} — "
                f"{p['amount_nano'] / 1_000_000_000:.4f} TON"
            )

    await message.answer("\n".join(lines), disable_web_page_preview=True)


@router.message(Command("cancel"))
async def cancel_order_cmd(message: Message, command, bot: Bot):
    """
    Отмена заказа по номеру: /cancel 19

    Нужна для «старых» заказов, под сообщениями которых кнопки отмены ещё нет,
    и вообще как запасной путь, если нужное сообщение потерялось в переписке.
    """
    if not is_admin(message.from_user.id):
        return

    arg = (command.args or "").strip().lstrip("#")
    if not arg.isdigit():
        await message.answer("Укажите номер заказа: <code>/cancel 19</code>")
        return

    order_id = int(arg)
    order = await get_order(order_id)
    if not order:
        await message.answer(f"Заказ #{order_id} не найден.")
        return

    if order["status"] in ("completed", "rejected"):
        await message.answer(
            f"Заказ #{order_id} уже закрыт (статус: {order['status']}). Отменять нечего."
        )
        return

    if order.get("cart_id"):
        await set_cart_status(order["cart_id"], "rejected", "Отменён продавцом")
        key = "cart_cancelled_by_admin"
        scope = f"вся корзина заказа #{order_id}"
    else:
        await set_order_status(order_id, "rejected", admin_comment="Отменён продавцом")
        key = "order_cancelled_by_admin"
        scope = f"заказ #{order_id}"

    await message.answer(
        f"🚫 Отменён {scope} — {order['item_name']} для {order['recipient']}.\n"
        "У клиента он больше не висит активным, можно оформлять новый."
    )

    lang = await _get_user_language(order["user_id"])
    try:
        await bot.send_message(order["user_id"], t(lang, key).format(order_id=order_id))
    except Exception:
        await message.answer("⚠️ Клиенту сообщить не удалось (закрыл чат с ботом).")


async def _append_note(call: CallbackQuery, note: str, reply_markup=None) -> None:
    """
    Дописать пометку к сообщению админа. Отдельная функция, потому что чек
    приходит картинкой (у неё caption), а предупреждения об ошибках —
    обычным текстом: edit_caption на тексте падает, и наоборот.
    """
    try:
        if call.message.caption is not None:
            await call.message.edit_caption(
                caption=(call.message.caption or "") + note, reply_markup=reply_markup
            )
        else:
            await call.message.edit_text(
                (call.message.text or "") + note, reply_markup=reply_markup
            )
    except Exception:
        # Сообщение могло устареть или быть уже отредактировано — не мешаем отмене
        pass


@router.callback_query(F.data.startswith("admin:cancel:"))
async def cancel_order_admin(call: CallbackQuery, bot: Bot):
    """
    Отмена заказа продавцом на ЛЮБОМ этапе — включая уже оплаченный.
    Нужна для случаев, когда чек оказался фейковым, оплату подтвердили по
    ошибке или автопокупка не прошла: без этой кнопки заказ навсегда висел
    бы у клиента в витрине активным и блокировал новые заказы.
    """
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    if order["status"] in ("completed", "rejected"):
        await call.answer("Заказ уже закрыт", show_alert=True)
        return

    # Заказ из корзины отменяется целиком: оплата на неё была одна общая,
    # отменить половину корзины нельзя — деньги не делятся.
    if order.get("cart_id"):
        await set_cart_status(order["cart_id"], "rejected", "Отменён продавцом")
        key = "cart_cancelled_by_admin"
    else:
        await set_order_status(order_id, "rejected", admin_comment="Отменён продавцом")
        key = "order_cancelled_by_admin"

    await _append_note(call, f"\n\n🚫 Отменён продавцом (заказ #{order_id})")
    await call.answer("Заказ отменён")

    lang = await _get_user_language(order["user_id"])
    try:
        await bot.send_message(order["user_id"], t(lang, key).format(order_id=order_id))
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin:cancel_cart:"))
async def cancel_cart_admin(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    cart_id = call.data.split(":", 2)[2]
    orders = await get_cart_orders(cart_id)
    if not orders:
        await call.answer("Корзина не найдена", show_alert=True)
        return

    await set_cart_status(cart_id, "rejected", "Отменена продавцом")
    await _append_note(call, "\n\n🚫 Корзина отменена продавцом")
    await call.answer("Корзина отменена")

    lang = await _get_user_language(orders[0]["user_id"])
    try:
        await bot.send_message(orders[0]["user_id"], t(lang, "cart_cancelled_by_admin"))
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin:rentconnect:"))
async def retry_rent_connect(call: CallbackQuery, bot: Bot):
    """
    Повторить подключение аренды прямо сейчас — после того, как админ
    подтвердил ton://-перевод в кошельке. Ждать очередного автоповтора
    (до 10 минут) в этот момент незачем.
    """
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    link = (order.get("rent_link") or "").strip()
    if not link:
        await call.answer("Клиент ещё не прислал ссылку", show_alert=True)
        return

    await call.answer("Пробую подключить...")

    from services.rent_connect import attempt_connect, explain_error

    ok, err = await attempt_connect(bot, order, link)
    if ok:
        lang = await _get_user_language(order["user_id"])
        from services.rent_connect import SUCCESS as RENT_SUCCESS

        try:
            await bot.send_message(
                order["user_id"],
                RENT_SUCCESS.get(lang if lang in RENT_SUCCESS else "uz").format(
                    item=order["item_name"]
                ),
            )
        except Exception:
            pass
        await _append_note(call, f"\n\n✅ Аренда подключена (заказ #{order_id})")
    else:
        await _append_note(
            call,
            f"\n\n❌ Снова не вышло: {err}\n{explain_error(Exception(err))}",
            reply_markup=call.message.reply_markup,
        )


@router.callback_query(F.data.startswith("admin:keep:"))
async def keep_order_admin(call: CallbackQuery, bot: Bot):
    """Ответ на просьбу клиента отменить оплаченный заказ — оставляем в работе."""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await _append_note(call, "\n\n↩️ Оставлен в работе")
    await call.answer("Оставлен в работе")

    lang = await _get_user_language(order["user_id"])
    try:
        await bot.send_message(
            order["user_id"], t(lang, "order_cancel_kept").format(order_id=order_id)
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin:done:"))
async def mark_done(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await set_order_status(order_id, "completed")
    await _append_note(call, "\n\n🎉 Выполнено")
    await call.answer("Отмечено как выполнено")

    lang = await _get_user_language(order["user_id"])
    await bot.send_message(
        order["user_id"],
        t(lang, "order_completed").format(order_id=order_id, item_name=order["item_name"]),
    )
    await post_completed_order(bot, order)
    await push_live_feed_event(FEED_EMOJI.get(order["category"], "🎁"), order["item_name"])
