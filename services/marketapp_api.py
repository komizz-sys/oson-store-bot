"""
Клиент к https://api.marketapp.org — официальный API (OpenAPI 3.1), включает:
- покупку Stars/Premium через Fragment (мы платим — доставляется получателю)
- аренду NFT-подарков (список гифтов, оплата аренды)

Авторизация: заголовок Authorization: <твой токен>, без "Bearer".
"""

import httpx

import config

BASE_URL = "https://api.marketapp.org"


def _headers() -> dict:
    return {"Authorization": config.MARKETAPP_API_KEY}


async def _post(path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        r = await client.post(path, headers=_headers(), json=json or {})
        r.raise_for_status()
        return r.json()


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        r = await client.get(path, headers=_headers(), params=params or {})
        r.raise_for_status()
        return r.json()


# ---------- Fragment: Stars ----------

async def get_stars_price(quantity: int) -> dict:
    """-> {'ton': float, 'gram': float, 'usd': float|None} — цена за quantity звёзд."""
    return await _post("/v1/fragment/stars/price/", {"quantity": quantity})


async def search_stars_recipient(username: str) -> dict:
    """-> {'photo': str, 'name': str} — проверка, что аккаунт существует."""
    return await _post("/v1/fragment/stars/recipient/", {"username": username})


async def buy_stars(username: str, quantity: int, currency: str = "GRAM") -> dict:
    """-> SendTxSchema {'transaction': {...}} — транзакцию нужно подписать и отправить."""
    return await _post(
        "/v1/fragment/stars/buy/",
        {"username": username, "quantity": quantity, "currency": currency},
    )


# ---------- Fragment: Premium ----------

async def get_premium_price() -> dict:
    """-> {'months3': {...}, 'months6': {...}, 'months12': {...}}"""
    return await _post("/v1/fragment/premium/price/")


async def search_premium_recipient(username: str) -> dict:
    return await _post("/v1/fragment/premium/recipient/", {"username": username})


async def buy_premium(username: str, months: int, currency: str = "GRAM") -> dict:
    """months должен быть 3, 6 или 12 — у Fragment нет 1-месячного варианта."""
    return await _post(
        "/v1/fragment/premium/buy/",
        {"username": username, "months": months, "currency": currency},
    )


# ---------- Rent ----------

async def get_gifts_for_rent(sort_by: str = "price_per_day", cursor: str | None = None) -> dict:
    """-> {'cursor': str|None, 'items': [RentItem]}"""
    params = {"sort_by": sort_by}
    if cursor:
        params["cursor"] = cursor
    return await _get("/v1/rent/gifts/", params)


async def rent_pay(nft_address: str, duration_seconds: int, price_per_day_gram: str) -> dict:
    """
    Оплата аренды конкретного гифта.
    duration_seconds должен делиться на 86400 (сутки) и укладываться в
    [min_duration, max_duration] из списка гифтов.
    -> SendTxSchema {'transaction': {...}}
    """
    return await _post(
        f"/v1/rent/{nft_address}/pay/",
        {"duration": duration_seconds, "price_per_day": price_per_day_gram},
    )
