"""
Отзывы о заказах.

Как это устроено:
- Заказ выполнен → в витрине на экране «Bajarildi» сразу пять звёзд и поле
  для комментария.
- Если человек там не оценил (закрыл витрину), через несколько минут бот
  пишет в чат «оцените заказ» с кнопками ⭐. После оценки предлагает
  дописать комментарий.
- Один отзыв на заказ; у корзины — один на всю корзину.
- Каждый отзыв публикуется ТОЛЬКО в канал заказов (PUBLIC_ORDERS_CHANNEL).
  Комментарий, пришедший позже оценки, дописывается в тот же пост.
- Оценка 1–3 сразу приходит владельцу — чтобы успеть поговорить с
  недовольным клиентом.
- Спам и мат владелец прячет командой /hidereview <номер заказа> — пост
  удаляется из канала, из средней оценки отзыв исключается.
"""

import asyncio
import html
import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from database.db import (
    add_review, get_order, get_orders_to_ask_review, get_review, get_user,
    get_user_language, mark_review_asked, review_key_order, set_review_channel_msg,
    get_orders_to_remind_review, mark_review_reminded,
    set_review_comment, get_cart_orders,
)

COMMENT_MAX = 500
LOW_RATING = 3            # 1..3 — повод владельцу написать клиенту
ASK_DELAY_SEC = 3 * 60    # сколько ждать после выполнения, прежде чем просить в чате
REMIND_AFTER_HOURS = 2   # единственное напоминание — через столько часов после просьбы

_lang = lambda v: v if v in ("uz", "ru", "en") else "uz"

ASK = {
    "uz": "✅ Buyurtmangiz bajarildi!\n\n<b>{item}</b> — hammasi yoqdimi? Xizmatimizni baholang 👇",
    "ru": "✅ Заказ выполнен!\n\n<b>{item}</b> — всё понравилось? Оцените нас 👇",
    "en": "✅ Your order is done!\n\n<b>{item}</b> — happy with it? Rate us 👇",
}
REMIND = {
    "uz": "⏰ <b>{item}</b> — buyurtmangiz qanday bo'ldi?\n\nBir bosishda baholang 👇 Bu boshqa xaridorlarga tanlashda yordam beradi.",
    "ru": "⏰ <b>{item}</b> — как вам заказ?\n\nОцените в одно нажатие 👇 Это помогает другим покупателям с выбором.",
    "en": "⏰ <b>{item}</b> — how was your order?\n\nRate it in one tap 👇 It helps other buyers choose.",
}
THANKS_ASK_COMMENT = {
    "uz": "Rahmat! {stars}\n\nIzoh qoldirasizmi? Bir-ikki so'z yozib yuboring 👇",
    "ru": "Спасибо! {stars}\n\nОставите комментарий? Напишите пару слов 👇",
    "en": "Thank you! {stars}\n\nLeave a comment? Just type a few words 👇",
}
SORRY_ASK_COMMENT = {
    "uz": "Rahmat, uzr so'raymiz 😔 {stars}\n\nNima yoqmadi? Yozib yuboring — albatta ko'rib chiqamiz.",
    "ru": "Спасибо, и простите 😔 {stars}\n\nЧто пошло не так? Напишите — обязательно разберёмся.",
    "en": "Thank you, and sorry 😔 {stars}\n\nWhat went wrong? Tell us — we'll look into it.",
}
SKIP_BTN = {"uz": "O'tkazib yuborish", "ru": "Пропустить", "en": "Skip"}
DONE = {
    "uz": "🙏 Rahmat, sharhingiz qabul qilindi!",
    "ru": "🙏 Спасибо, отзыв принят!",
    "en": "🙏 Thanks, your review is in!",
}
ALREADY = {
    "uz": "Bu buyurtmaga allaqachon baho qo'yilgan 🙏",
    "ru": "Этот заказ уже оценён 🙏",
    "en": "This order has already been rated 🙏",
}
CART_ITEM = {"uz": "🛒 {n} ta mahsulot", "ru": "🛒 {n} товар(а)", "en": "🛒 {n} items"}


def stars(n: int) -> str:
    return "⭐" * int(n)


def clean_comment(text: str | None) -> str | None:
    text = " ".join((text or "").split())
    return text[:COMMENT_MAX] if text else None


def rate_kb(order_id: int) -> InlineKeyboardMarkup:
    # Сверху пятёрка, вниз по убыванию: каждая кнопка — ровно то, что на ней
    # нарисовано, без подписей «отлично/плохо».
    b = InlineKeyboardBuilder()
    for n in (5, 4, 3, 2, 1):
        b.button(text=stars(n), callback_data=f"review:rate:{order_id}:{n}")
    b.adjust(1)
    return b.as_markup()


def skip_kb(order_id: int, lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=SKIP_BTN[lang], callback_data=f"review:skip:{order_id}")
    return b.as_markup()


async def item_label(order: dict, lang: str) -> str:
    if order.get("cart_id"):
        items = await get_cart_orders(order["cart_id"])
        if len(items) > 1:
            return CART_ITEM[lang].format(n=len(items))
    return order.get("item_name") or f"#{order['id']}"


# ---------------------------------------------------------------- канал

async def _channel_text(review: dict, order: dict) -> str:
    user = await get_user(review["user_id"]) or {}
    name = ((user.get("full_name") or "").strip().split() or ["Mijoz"])[0][:24]
    item = await item_label(order, "uz")
    lines = [
        f"{stars(review['rating'])} <b>YANGI SHARH</b>",
        "",
        f"👤 <b>Mijoz:</b> {html.escape(name)}",
        f"🛍 <b>Buyurtma:</b> #{review['order_id']} · {html.escape(item)}",
    ]
    if review.get("comment"):
        lines += ["", f"💬 «{html.escape(review['comment'])}»"]
    return "\n".join(lines)


async def publish_review(bot: Bot, order_id: int) -> None:
    """Пост в канал заказов — новый, или правка уже опубликованного."""
    if not config.PUBLIC_ORDERS_CHANNEL:
        return
    review = await get_review(order_id)
    order = await get_order(order_id)
    if not review or not order or review.get("hidden"):
        return
    text = await _channel_text(review, order)
    try:
        if review.get("channel_msg_id"):
            await bot.edit_message_text(text, chat_id=config.PUBLIC_ORDERS_CHANNEL,
                                        message_id=review["channel_msg_id"])
        else:
            msg = await bot.send_message(config.PUBLIC_ORDERS_CHANNEL, text)
            await set_review_channel_msg(order_id, msg.message_id)
    except Exception as e:
        # Канал недоступен или бот там не админ — отзыв всё равно сохранён.
        logging.warning(f"Отзыв #{order_id} не опубликован в канал: {e}")


async def unpublish_review(bot: Bot, review: dict) -> None:
    if not config.PUBLIC_ORDERS_CHANNEL or not review.get("channel_msg_id"):
        return
    try:
        await bot.delete_message(config.PUBLIC_ORDERS_CHANNEL, review["channel_msg_id"])
    except Exception as e:
        logging.warning(f"Не удалось удалить отзыв #{review['order_id']} из канала: {e}")


# ---------------------------------------------------------------- владелец

def _admin_kb(review: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💬 Написать клиенту", url=f"tg://user?id={review['user_id']}")
    b.button(text="🙈 Скрыть отзыв", callback_data=f"review:hide:{review['order_id']}")
    b.adjust(1)
    return b.as_markup()


async def alert_admins_if_low(bot: Bot, order_id: int, comment_only: bool = False) -> None:
    """
    Низкая оценка → сразу владельцу. Если комментарий пришёл позже оценки —
    досылаем его отдельным сообщением, чтобы было видно, на что жалоба.
    """
    review = await get_review(order_id)
    order = await get_order(order_id)
    if not review or not order or review["rating"] > LOW_RATING:
        return
    user = await get_user(review["user_id"]) or {}
    who = html.escape(user.get("full_name") or "—")
    if user.get("username"):
        who += f" @{html.escape(user['username'])}"
    if comment_only:
        text = (f"💬 Комментарий к оценке {stars(review['rating'])} по заказу #{order_id}:\n"
                f"«{html.escape(review.get('comment') or '')}»")
    else:
        text = (f"⚠️ <b>Низкая оценка</b> {stars(review['rating'])}\n\n"
                f"Заказ #{order_id} · {html.escape(await item_label(order, 'ru'))}\n"
                f"Клиент: {who} (<code>{review['user_id']}</code>)")
        if review.get("comment"):
            text += f"\n\n💬 «{html.escape(review['comment'])}»"
        text += "\n\nНапиши ему, пока он не пошёл жаловаться в чаты."
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=_admin_kb(review))
        except Exception:
            pass


# ---------------------------------------------------------------- приём

async def resolve_review_order(order_id: int, user_id: int) -> dict | None:
    """
    Заказ, который этот клиент может оценить: его собственный и выполненный
    (корзина — целиком). -> заказ-«ключ» отзыва, или None.
    """
    order = await get_order(order_id)
    if not order or order["user_id"] != user_id:
        return None
    if order.get("cart_id"):
        items = await get_cart_orders(order["cart_id"])
        if not items or any(o["status"] != "completed" for o in items):
            return None
    elif order["status"] != "completed":
        return None
    key = await review_key_order(order)
    return await get_order(key) if key != order["id"] else order


async def submit_review(bot: Bot, order_id: int, user_id: int, rating: int,
                        comment: str | None) -> tuple[str, dict | None]:
    """
    -> ("ok", отзыв) | ("already", None) | ("not_allowed", None) | ("bad_rating", None)
    Общий путь для витрины и чата.
    """
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return "bad_rating", None
    if not 1 <= rating <= 5:
        return "bad_rating", None
    order = await resolve_review_order(order_id, user_id)
    if not order:
        return "not_allowed", None
    review = await add_review(order["id"], order.get("cart_id"), user_id, rating, clean_comment(comment))
    if not review:
        return "already", None
    await publish_review(bot, order["id"])
    await alert_admins_if_low(bot, order["id"])
    return "ok", review


async def add_comment_later(bot: Bot, order_id: int, user_id: int, comment: str) -> bool:
    """Комментарий, присланный в чат после оценки кнопкой."""
    review = await get_review(order_id)
    text = clean_comment(comment)
    if not review or review["user_id"] != user_id or not text:
        return False
    if not await set_review_comment(order_id, text):
        return False
    await publish_review(bot, order_id)
    await alert_admins_if_low(bot, order_id, comment_only=True)
    return True


# ---------------------------------------------------------------- просьба в чате

_FIRST_SEEN: dict[int, float] = {}


async def ask_for_review(bot: Bot, order: dict, reminder: bool = False) -> None:
    lang = _lang(await get_user_language(order["user_id"]))
    item = html.escape(await item_label(order, lang))
    text = (REMIND if reminder else ASK)[lang].format(item=item)
    try:
        await bot.send_message(order["user_id"], text, reply_markup=rate_kb(order["id"]))
    except Exception:
        pass  # клиент заблокировал бота — ничего страшного


async def review_request_loop(bot: Bot) -> None:
    """
    Раз в минуту: выполненные заказы без оценки → через ASK_DELAY_SEC после
    того, как заметили выполнение, просим оценить в чате. Задержка даёт
    человеку сначала оценить в витрине, где он как раз видит «Bajarildi».
    """
    await asyncio.sleep(30)
    while True:
        try:
            now = time.monotonic()
            for order in await get_orders_to_ask_review():
                seen = _FIRST_SEEN.setdefault(order["id"], now)
                if now - seen < ASK_DELAY_SEC:
                    continue
                _FIRST_SEEN.pop(order["id"], None)
                # Сначала помечаем, потом шлём: если отправка упадёт, лучше
                # не спросить, чем спросить дважды.
                await mark_review_asked(order)
                if await get_review(order["id"]):
                    continue  # уже оценил в витрине
                await ask_for_review(bot, order)

            # Одно напоминание тем, кто так и не оценил. Больше не пишем:
            # навязчивость раздражает сильнее, чем помогает.
            for order in await get_orders_to_remind_review(REMIND_AFTER_HOURS):
                await mark_review_reminded(order)
                await ask_for_review(bot, order, reminder=True)
        except Exception as e:
            logging.error(f"Цикл просьб об отзыве: {e}")
        await asyncio.sleep(60)
