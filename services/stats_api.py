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

import config
from database.db import get_revenue_stats, get_user_orders, get_user_spend_stats, get_leaderboard
from services.telegram_auth import validate_init_data
from services.order_processing import process_order, OrderError

# Заполняются в start_stats_server() — нужны для /public/create_order,
# чтобы вручную собрать FSMContext вне обычного апдейта от aiogram
# (тот же Storage, что использует Dispatcher, поэтому дальнейшее
# подтверждение/отмена заказа кнопками в чате работает как обычно).
_bot = None
_storage = None

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


async def handle_leaderboard(request: web.Request) -> web.Response:
    period = request.query.get("period", "all")
    if period not in PERIOD_TO_SQL:
        return web.json_response({"error": f"unknown period, expected one of {list(PERIOD_TO_SQL)}"}, status=400)

    since_sql = await _period_since_sql(period)
    rows = await get_leaderboard(since_sql, limit=20)
    return web.json_response({"leaderboard": rows, "period": period})


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

    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/internal/stats", handle_stats)
    app.router.add_post("/public/my_orders", handle_my_orders)
    app.router.add_post("/public/my_stats", handle_my_stats)
    app.router.add_get("/public/leaderboard", handle_leaderboard)
    app.router.add_post("/public/_diag", handle_diag)
    app.router.add_post("/public/create_order", handle_create_order)
    for path in ("/public/my_orders", "/public/my_stats", "/public/_diag", "/public/create_order"):
        app.router.add_route("OPTIONS", path, handle_preflight)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.STATS_API_PORT)
    await site.start()
