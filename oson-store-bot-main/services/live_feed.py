"""
Пуш события в живую ленту заказов ("Jonli") на веб-сервисе. Бот и веб —
разные сервисы без общей БД, поэтому это просто короткий HTTP-запрос
на свой же веб-сервис при каждом выполненном заказе.

Если WEBAPP_URL или INTERNAL_PUSH_SECRET не заданы — просто ничего не делает,
остальной бот работает как обычно.
"""

import httpx

import config


async def push_live_feed_event(emoji: str, label: str) -> None:
    if not config.WEBAPP_URL or not config.INTERNAL_PUSH_SECRET:
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                f"{config.WEBAPP_URL}/api/live_feed/push",
                json={"emoji": emoji, "label": label},
                headers={"X-Internal-Secret": config.INTERNAL_PUSH_SECRET},
            )
    except Exception:
        pass
