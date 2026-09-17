"""
Продление аренды NFT-подарка.

Зачем: аренда заканчивается в конкретный день, и раньше клиенту, чтобы
оставить подарок у себя дольше, приходилось арендовать его заново — заново
искать в каталоге, заново получать tc://-ссылку и подключать. Теперь в
мини-аппе есть раздел «Мои аренды»: видно, сколько осталось, и одной кнопкой
можно докупить дни.

Как считается срок: в базе нет отдельной таблицы аренд — есть заказы. Аренда
одного и того же nft_address = первый (базовый) заказ + все его продления.
Значит: начало = дата базового заказа, длительность = сумма rent_days всех
оплаченных заказов по этому nft_address, конец = начало + длительность.

Как выполняется продление: ровно тем же вызовом MarketApp, что и новая
аренда (rent_pay на тот же nft_address ещё на N дней) — админ подтверждает
транзакцию в кошельке как обычно. Отдельного «магического» метода продления
не изобретаем: если MarketApp вернёт ошибку, админ увидит её текст и сможет
продлить вручную на marketapp.org, как и для обычной аренды.
"""

from datetime import datetime, timedelta, timezone

import config
from database.db import get_user_rent_orders
from services.marketapp_service import calc_rent_price

# Границы срока продления. У MarketApp они свои у каждого лота, но лот,
# который уже в аренде, в каталоге не отдаётся — поэтому берём разумные
# рамки из настроек, а фактический срок всё равно подтверждает админ.
EXTEND_MIN_DAYS = int(getattr(config, "RENT_EXTEND_MIN_DAYS", 1))
EXTEND_MAX_DAYS = int(getattr(config, "RENT_EXTEND_MAX_DAYS", 30))


def _parse_sql_dt(value: str | None) -> datetime | None:
    """created_at из sqlite — строка UTC вида 'YYYY-MM-DD HH:MM:SS'."""
    if not value:
        return None
    text = str(value).replace("T", " ").split(".")[0]
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def get_active_rentals(user_id: int) -> list[dict]:
    """
    Действующие аренды клиента — то, что мини-апп показывает в «Мои аренды».
    -> [{nft_address, item_name, ends_at, seconds_left, days_total,
         price_per_day_uzs, base_price_per_day_gram, order_id}]
    """
    orders = await get_user_rent_orders(user_id)
    now = datetime.now(timezone.utc)

    grouped: dict[str, dict] = {}
    for o in orders:
        address = o.get("nft_address")
        if not address or not o.get("rent_days"):
            continue
        started = _parse_sql_dt(o.get("created_at"))
        if not started:
            continue

        g = grouped.setdefault(address, {
            "nft_address": address,
            "order_id": o["id"],
            "item_name": o["item_name"],
            "base_price_per_day_gram": o.get("base_price_per_day_gram"),
            "started_at": started,
            "days_total": 0,
            "extensions": 0,
        })
        g["days_total"] += int(o["rent_days"])
        if o.get("is_extension"):
            g["extensions"] += 1
        else:
            # Базовый заказ задаёт точку отсчёта и «чистое» название без
            # приставки «Продление:»
            g["started_at"] = min(g["started_at"], started)
            g["item_name"] = o["item_name"]
            g["order_id"] = o["id"]
        if not g["base_price_per_day_gram"] and o.get("base_price_per_day_gram"):
            g["base_price_per_day_gram"] = o["base_price_per_day_gram"]

    result = []
    for g in grouped.values():
        ends_at = g["started_at"] + timedelta(days=g["days_total"])
        seconds_left = int((ends_at - now).total_seconds())
        if seconds_left <= 0:
            continue  # аренда уже закончилась — продлевать нечего

        try:
            gram = float(g["base_price_per_day_gram"])
        except (TypeError, ValueError):
            gram = 0.0
        price_per_day = calc_rent_price(gram, 1)["with_markup"] if gram else 0

        result.append({
            "nft_address": g["nft_address"],
            "order_id": g["order_id"],
            "item_name": g["item_name"],
            "days_total": g["days_total"],
            "extensions": g["extensions"],
            "ends_at": ends_at.strftime("%Y-%m-%d %H:%M:%S"),
            "seconds_left": seconds_left,
            "base_price_per_day_gram": gram,
            "price_per_day_uzs": price_per_day,
            "min_days": EXTEND_MIN_DAYS,
            "max_days": EXTEND_MAX_DAYS,
            "can_extend": gram > 0,
        })

    result.sort(key=lambda r: r["seconds_left"])
    return result


async def find_rental(user_id: int, nft_address: str) -> dict | None:
    for r in await get_active_rentals(user_id):
        if r["nft_address"] == nft_address:
            return r
    return None
