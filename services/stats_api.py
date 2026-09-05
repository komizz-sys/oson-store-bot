"""
Маленький защищённый HTTP-сервер, который отдаёт доход по заказам.
Работает в ТОМ ЖЕ процессе, что и сам бот (bot.py), — поэтому имеет
прямой доступ к той же базе данных без танцев с общими volume на Railway
(Railway не умеет шарить один volume между двумя разными сервисами).

Использует его отдельный бот-аналитик (analytics_bot) — стучится сюда
по HTTP с секретным заголовком, чтобы узнать доход за период, а расходы
считает сам (см. ANALYTICS_API_SECRET в .env — должен совпадать в обоих
ботах).
"""

from aiohttp import web

import config
from database.db import get_revenue_stats

PERIOD_TO_SQL = {
    "today": "datetime('now', 'start of day')",
    "week": "datetime('now', '-7 day')",
    "month": "datetime('now', '-30 day')",
    "all": None,
}


async def handle_stats(request: web.Request) -> web.Response:
    if not config.ANALYTICS_API_SECRET:
        return web.json_response({"error": "ANALYTICS_API_SECRET не задан на сервере магазина"}, status=503)

    if request.headers.get("X-Internal-Secret") != config.ANALYTICS_API_SECRET:
        return web.json_response({"error": "forbidden"}, status=403)

    period = request.query.get("period", "today")
    if period not in PERIOD_TO_SQL:
        return web.json_response({"error": f"unknown period, expected one of {list(PERIOD_TO_SQL)}"}, status=400)

    since_sql = None
    if PERIOD_TO_SQL[period] is not None:
        # Считаем выражение прямо в SQLite, чтобы не возиться с часовыми поясами на Python-стороне
        import aiosqlite
        async with aiosqlite.connect(config.DB_PATH) as db:
            async with db.execute(f"SELECT {PERIOD_TO_SQL[period]}") as cur:
                since_sql = (await cur.fetchone())[0]

    data = await get_revenue_stats(since_sql, config.TON_GRAM_RATE_UZS)
    data["period"] = period
    return web.json_response(data)


async def start_stats_server():
    """Запускается фоновой задачей рядом с polling бота (см. bot.py)."""
    if not config.ANALYTICS_API_SECRET:
        # Аналитику не настраивали — не поднимаем сервер вообще, не занимаем порт зря
        return

    app = web.Application()
    app.router.add_get("/internal/stats", handle_stats)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.STATS_API_PORT)
    await site.start()
