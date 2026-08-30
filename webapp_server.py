"""
Отдельный процесс (запускается на Railway как второй сервис "Web").
Отдаёт статику мини-аппа (webapp/) и JSON-каталог для него.
Заказы НЕ создаёт и в базу не пишет — это делает бот через web_app_data,
чтобы не дублировать логику оплаты/подтверждения. Этот сервис только читает.
"""

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import config
from services.prices import get_stars_packages, get_premium_packages
from services.marketapp_service import get_available_gifts

app = FastAPI(title="Gift Shop Mini App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_bot_username_cache: str | None = None


@app.get("/api/stars")
async def api_stars():
    return get_stars_packages()


@app.get("/api/premium")
async def api_premium():
    return get_premium_packages()


@app.get("/api/simple_gift")
async def api_simple_gift():
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"https://api.telegram.org/bot{config.BOT_TOKEN}/getAvailableGifts")
        r.raise_for_status()
        data = r.json()

    gifts = []
    for g in data.get("result", {}).get("gifts", []):
        if g.get("remaining_count") is not None:
            continue  # лимитированные пропускаем — это "простые" подарки
        star_count = g["star_count"]
        gifts.append({
            "id": g["id"],
            "star_count": star_count,
            "price_uzs": round(star_count * config.STAR_UNIT_PRICE_UZS),
            "sticker_emoji": (g.get("sticker") or {}).get("emoji", "🎁"),
        })
    gifts.sort(key=lambda x: x["star_count"])
    return gifts


@app.get("/api/nft_rent")
async def api_nft_rent(sort_by: str = "recently_touch"):
    return await get_available_gifts(limit=15, sort_by=sort_by)


@app.get("/api/payment_info")
async def api_payment_info():
    """Реквизиты для оплаты — чтобы не хардкодить в JS и не пересобирать фронт при смене карты."""
    return {
        "card_number": config.PAYMENT_CARD_NUMBER,
        "card_holder": config.PAYMENT_CARD_HOLDER,
    }


@app.get("/api/rent_terms")
async def api_rent_terms():
    """Параметры комиссии аренды — считается на лету, всегда синхронно с .env бота."""
    fee_uzs = round(config.RENT_FEE_GRAM * config.TON_GRAM_RATE_UZS)
    refund_uzs = round(fee_uzs * config.RENT_FEE_REFUND_PERCENT / 100)
    return {
        "fee_gram": config.RENT_FEE_GRAM,
        "fee_uzs": fee_uzs,
        "refund_percent": config.RENT_FEE_REFUND_PERCENT,
        "refund_uzs": refund_uzs,
    }


@app.get("/api/bot_info")
async def api_bot_info():
    """Юзернейм бота — для реферальной ссылки. Кэшируется в памяти процесса."""
    global _bot_username_cache
    if _bot_username_cache is None:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"https://api.telegram.org/bot{config.BOT_TOKEN}/getMe")
            r.raise_for_status()
            _bot_username_cache = r.json()["result"]["username"]
    return {"username": _bot_username_cache}


@app.get("/api/support_info")
async def api_support_info():
    """Контакты для раздела Profil: оператор + каналы. Пустая строка — строка скрывается на фронте."""
    def clean(v: str) -> str:
        return v.lstrip("@") if v else ""

    return {
        "operator_username": clean(config.OPERATOR_USERNAME),
        "channel_username": clean(config.REQUIRED_CHANNEL) if config.REQUIRED_CHANNEL.startswith("@") else "",
        "orders_channel_username": clean(config.PUBLIC_ORDERS_CHANNEL) if config.PUBLIC_ORDERS_CHANNEL.startswith("@") else "",
    }


# Статика мини-аппа — подключаем последней, чтобы не перекрывать /api/*
app.mount("/", StaticFiles(directory="webapp", html=True), name="webapp")
