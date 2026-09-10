import json
from pathlib import Path

PRICES_FILE = Path(__file__).resolve().parent.parent / "data" / "prices.json"


def load_prices() -> dict:
    with open(PRICES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def format_uzs(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " сум"


def get_stars_packages() -> list[dict]:
    return load_prices()["stars"]


def get_premium_packages() -> list[dict]:
    return load_prices()["premium"]


def get_nft_rent_items() -> list[dict]:
    return load_prices()["nft_rent"]


def get_ton_gram_rate_info() -> str:
    import config
    fee = round(config.RENT_FEE_GRAM * config.TON_GRAM_RATE_UZS)
    refund = round(fee * config.RENT_FEE_REFUND_PERCENT / 100)
    return (
        f"Комиссия сети: {config.RENT_FEE_GRAM} TON (~{format_uzs(fee)}), "
        f"из них {config.RENT_FEE_REFUND_PERCENT}% (~{format_uzs(refund)}) "
        f"вернётся вам после окончания аренды."
    )
