"""
Аренда NFT-подарков через официальный API MarketApp.

ВАЖНО про кошелёк: оплату аренды нужно проводить ТЕМ ЖЕ кошельком, которым был
сгенерирован API-токен на marketapp.org. Ты сам подтверждаешь каждую транзакцию
в своём кошельке (Tonkeeper и т.п.) по ссылке, которую присылает бот — сам бот
никогда не хранит ключи и не может потратить средства без твоего подтверждения.

Картинки гифтов API MarketApp не отдаёт (в схеме RentItem их просто нет), поэтому
подтягиваем их отдельно с nft.fragment.com — это публичный, задокументированный
паттерн метаданных гифтов Fragment (name, image, lottie-анимация и т.д.).
"""

import asyncio
import re

import httpx
from aiogram import Bot

import config
from services import marketapp_api
from services.ton_deeplink import build_ton_deeplinks

SECONDS_IN_DAY = 86400
NANO_PER_GRAM = 1_000_000_000

_NAME_NUM_RE = re.compile(r"^(.*?)\s*#(\d+)\s*$")


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


async def _fetch_gift_image(client: httpx.AsyncClient, nft_name: str) -> str | None:
    """Тянет реальную картинку гифта с nft.fragment.com по его имени/номеру."""
    m = _NAME_NUM_RE.match(nft_name or "")
    if not m:
        return None
    title, number = m.group(1), m.group(2)
    slug = _slugify(title)
    if not slug:
        return None
    try:
        r = await client.get(f"https://nft.fragment.com/gift/{slug}-{number}.json", timeout=8)
        if r.status_code != 200:
            return None
        return r.json().get("image")
    except Exception:
        return None


async def get_available_gifts(limit: int = 10) -> list[dict]:
    """
    Живой список гифтов, доступных в аренду, с ценой/день в сумах (уже с наценкой)
    и, если удалось получить, реальной картинкой гифта.
    """
    try:
        data = await marketapp_api.get_gifts_for_rent(sort_by="price_per_day")
    except Exception:
        return []

    raw_items = data.get("items", [])[:limit]

    async with httpx.AsyncClient() as client:
        images = await asyncio.gather(
            *[_fetch_gift_image(client, it["nft_name"]) for it in raw_items],
            return_exceptions=False,
        )

    result = []
    for item, image_url in zip(raw_items, images):
        base_price_per_day_gram = int(item["price_per_day"]) / NANO_PER_GRAM
        calc = calc_rent_price(base_price_per_day_gram, days=1)

        m = _NAME_NUM_RE.match(item["nft_name"] or "")
        title = m.group(1) if m else item["nft_name"]
        number = m.group(2) if m else None

        result.append({
            "nft_address": item["nft_address"],
            "name": title,
            "number": number,
            "image_url": image_url,
            "discount_per_day": item.get("discount_per_day", 0),
            "base_price_per_day_gram": base_price_per_day_gram,
            "price_per_day_uzs_with_markup": calc["with_markup"],
            "min_duration_days": item["min_duration"] // SECONDS_IN_DAY,
            "max_duration_days": item["max_duration"] // SECONDS_IN_DAY,
        })
    return result


def calc_rent_price(base_price_per_day_gram: float, days: int) -> dict:
    """
    Формула: (базовая_цена_в_день_в_грамах_TON * дни) -> в сумы -> наценка 20%
    + комиссия сети (0.1 TON, 40% из неё возвращается арендатору после аренды).
    """
    base_total_uzs = base_price_per_day_gram * days * config.TON_GRAM_RATE_UZS
    with_markup = round(base_total_uzs * config.RENT_MARKUP)

    fee_total_uzs = round(config.RENT_FEE_GRAM * config.TON_GRAM_RATE_UZS)
    fee_refundable_uzs = round(fee_total_uzs * config.RENT_FEE_REFUND_PERCENT / 100)
    fee_nonrefundable_uzs = fee_total_uzs - fee_refundable_uzs

    return {
        "with_markup": with_markup,
        "fee_total_uzs": fee_total_uzs,
        "fee_refundable_uzs": fee_refundable_uzs,
        "fee_nonrefundable_uzs": fee_nonrefundable_uzs,
        "total_to_pay": with_markup + fee_total_uzs,
    }


async def start_rent_payment(bot: Bot, order: dict, nft_address: str,
                              base_price_per_day_gram: float, days: int) -> None:
    """Готовит транзакцию оплаты аренды и присылает админу ссылку на подтверждение."""
    duration_seconds = days * SECONDS_IN_DAY
    price_per_day_nano = str(int(base_price_per_day_gram * NANO_PER_GRAM))

    try:
        tx = await marketapp_api.rent_pay(nft_address, duration_seconds, price_per_day_nano)
    except Exception as e:
        text = (
            f"⚠️ Заказ #{order['id']} (аренда {order['item_name']}) оплачен клиентом, "
            f"но запрос на аренду через API не удался: {e}\n"
            "Оформи аренду вручную на marketapp.org."
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass
        return

    links = build_ton_deeplinks(tx)
    text = (
        f"🖼 Заказ #{order['id']} — аренда «{order['item_name']}» на {days} дн.\n"
        f"Получатель: {order['recipient']}\n\n"
        f"⚠️ Подтверди оплату ИМЕННО тем кошельком, которым генерировал API-токен "
        f"на marketapp.org:\n" + "\n".join(links) +
        "\n\nПосле оплаты гифт появится во вкладке Rented на marketapp.org — "
        "передай его получателю и нажми «Заказ выполнен»."
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, disable_web_page_preview=True)
        except Exception:
            pass
