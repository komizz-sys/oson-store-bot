"""
Бан клиента — одна точка на весь чат.

Проверять бан в каждом хендлере отдельно бессмысленно: рано или поздно
появится новый хендлер, где проверку забудут, и забаненный пролезет именно
через него. Поэтому проверка стоит ДО всех роутеров: забаненный человек
просто не доходит до кода бота.

Кэш на 60 секунд — чтобы при рекламном наплыве не ходить в базу на каждое
нажатие кнопки. Разбан из-за кэша срабатывает не мгновенно, а в течение
минуты; для бана это нормально.
"""

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import config
from database.db import is_banned

CACHE_TTL_SECONDS = 60
_cache: dict[int, tuple[bool, float]] = {}

BANNED_TEXT = (
    "🚫 Sizning hisobingiz bloklangan.\n"
    "Ваш аккаунт заблокирован.\n\n"
    "Savol bo'lsa — operatorga yozing."
)


def drop_from_cache(user_id: int) -> None:
    """Сбросить кэш после /ban и /unban — чтобы решение админа сработало сразу."""
    _cache.pop(user_id, None)


async def _banned(user_id: int) -> bool:
    now = time.monotonic()
    cached = _cache.get(user_id)
    if cached and now - cached[1] < CACHE_TTL_SECONDS:
        return cached[0]
    try:
        value = await is_banned(user_id)
    except Exception:
        # База недоступна — пропускаем человека дальше. Лучше пропустить
        # забаненного, чем закрыть магазин для всех из-за сбоя.
        return False
    _cache[user_id] = (value, now)
    return value


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id in config.ADMIN_IDS:
            return await handler(event, data)

        if not await _banned(user.id):
            return await handler(event, data)

        # Забаненному отвечаем коротко и один раз на действие — без этого
        # человек будет думать, что бот сломался, и напишет оператору.
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(BANNED_TEXT, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(BANNED_TEXT)
        except Exception:
            pass
        return None
