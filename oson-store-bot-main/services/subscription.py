"""
Обязательная подписка на канал перед использованием бота.

Как включить:
1. Впиши в .env REQUIRED_CHANNEL — @username канала (для публичного) или его
   числовой ID (для приватного, узнать через @userinfobot)
2. Если канал приватный — дополнительно впиши REQUIRED_CHANNEL_LINK
   (пригласительную ссылку), иначе кнопка "Подписаться" не будет работать
3. Бот должен быть добавлен в канал (админом — для приватного канала,
   обычным участником достаточно для публичного, но админом надёжнее)

Если REQUIRED_CHANNEL не задан — проверка просто не выполняется, все
пользователи считаются подписанными.
"""

from aiogram import Bot

import config


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not config.REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(config.REQUIRED_CHANNEL, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        # Не смогли проверить (бот не в канале, неверный ID и т.п.) —
        # не блокируем пользователей из-за ошибки конфигурации
        return True


def channel_link() -> str:
    if config.REQUIRED_CHANNEL_LINK:
        return config.REQUIRED_CHANNEL_LINK
    if config.REQUIRED_CHANNEL.startswith("@"):
        return f"https://t.me/{config.REQUIRED_CHANNEL[1:]}"
    return ""
