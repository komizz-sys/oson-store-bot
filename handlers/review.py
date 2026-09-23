"""
Отзывы в чате: кнопки ⭐ под просьбой оценить, комментарий следующим
сообщением, «Пропустить», и скрытие отзыва владельцем.

Логика отзывов (сохранение, канал, тревога при низкой оценке) — в
services/reviews.py, общая с витриной.
"""

import re
import time

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
from database.db import get_review, get_user_language, set_review_hidden
from services import reviews as rv

router = Router()

# Сколько ждём комментарий после нажатия звезды. Дольше — уже не ответ на
# наш вопрос, а обычное сообщение боту, и забирать его в отзыв нельзя.
COMMENT_WINDOW_SEC = 15 * 60

# Ссылки в комментарий не берём: после аренды клиент может как раз прислать
# новую tc://-ссылку, и она должна уйти на переподключение, а не в отзыв.
_LINK_RE = re.compile(r"(tc://|https?://|t\.me/)", re.IGNORECASE)


class ReviewStates(StatesGroup):
    comment = State()


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.callback_query(F.data.startswith("review:rate:"))
async def on_rate(call: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        _, _, order_id, rating = call.data.split(":")
        order_id, rating = int(order_id), int(rating)
    except ValueError:
        await call.answer()
        return
    lang = rv._lang(await get_user_language(call.from_user.id))

    result, _ = await rv.submit_review(bot, order_id, call.from_user.id, rating, None)
    if result == "already":
        await call.answer(rv.ALREADY[lang], show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    if result != "ok":
        await call.answer()
        return

    template = rv.SORRY_ASK_COMMENT if rating <= rv.LOW_RATING else rv.THANKS_ASK_COMMENT
    try:
        await call.message.edit_text(template[lang].format(stars=rv.stars(rating)),
                                     reply_markup=rv.skip_kb(order_id, lang))
    except Exception:
        pass
    await state.set_state(ReviewStates.comment)
    await state.update_data(review_order_id=order_id, review_asked_at=time.time())
    await call.answer()


@router.callback_query(F.data.startswith("review:skip:"))
async def on_skip(call: CallbackQuery, state: FSMContext):
    lang = rv._lang(await get_user_language(call.from_user.id))
    await state.clear()
    try:
        await call.message.edit_text(rv.DONE[lang])
    except Exception:
        pass
    await call.answer()


@router.message(ReviewStates.comment, F.text)
async def on_comment(message: Message, state: FSMContext, bot: Bot):
    text = message.text or ""
    data = await state.get_data()
    # Команды (/start, /operator) и ссылки — не комментарий: отпускаем дальше.
    if text.startswith("/") or _LINK_RE.search(text):
        await state.clear()
        raise SkipHandler
    if time.time() - float(data.get("review_asked_at") or 0) > COMMENT_WINDOW_SEC:
        await state.clear()
        raise SkipHandler

    order_id = int(data.get("review_order_id") or 0)
    await state.clear()
    lang = rv._lang(await get_user_language(message.from_user.id))
    if order_id and await rv.add_comment_later(bot, order_id, message.from_user.id, text):
        await message.answer(rv.DONE[lang])
    else:
        raise SkipHandler


# ---------------------------------------------------------------- владелец

async def _hide(bot: Bot, order_id: int) -> str:
    review = await get_review(order_id)
    if not review:
        return f"Отзыва по заказу #{order_id} нет."
    if review.get("hidden"):
        return f"Отзыв по заказу #{order_id} уже скрыт."
    await set_review_hidden(order_id, True)
    await rv.unpublish_review(bot, review)
    return f"🙈 Отзыв по заказу #{order_id} скрыт и удалён из канала."


@router.callback_query(F.data.startswith("review:hide:"))
async def on_hide_button(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    order_id = int(call.data.split(":")[2])
    await call.answer(await _hide(bot, order_id), show_alert=True)


@router.message(Command("hidereview"))
async def cmd_hide(message: Message, command: CommandObject, bot: Bot):
    if not _is_admin(message.from_user.id):
        raise SkipHandler
    arg = (command.args or "").strip().lstrip("#")
    if not arg.isdigit():
        await message.answer("Формат: /hidereview 123 — номер заказа из поста в канале.")
        return
    await message.answer(await _hide(bot, int(arg)))


@router.message(Command("showreview"))
async def cmd_show(message: Message, command: CommandObject, bot: Bot):
    """Вернуть скрытый по ошибке отзыв (в канал публикуется заново)."""
    if not _is_admin(message.from_user.id):
        raise SkipHandler
    arg = (command.args or "").strip().lstrip("#")
    if not arg.isdigit():
        await message.answer("Формат: /showreview 123")
        return
    order_id = int(arg)
    review = await get_review(order_id)
    if not review:
        await message.answer(f"Отзыва по заказу #{order_id} нет.")
        return
    await set_review_hidden(order_id, False)
    from database.db import set_review_channel_msg
    await set_review_channel_msg(order_id, None)
    await rv.publish_review(bot, order_id)
    await message.answer(f"👁 Отзыв по заказу #{order_id} снова виден.")
