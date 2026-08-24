from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from services.prices import get_stars_packages, get_premium_packages, get_nft_rent_items, format_uzs
from services.i18n import t, LANGUAGES


def language_select_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, flag, name in LANGUAGES:
        b.button(text=f"{flag} {name}", callback_data=f"setlang:{code}")
    b.adjust(1)
    return b.as_markup()


def main_menu_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if config.WEBAPP_URL:
        b.button(text=t(lang, "menu_webapp"), web_app=WebAppInfo(url=config.WEBAPP_URL))
    b.button(text=t(lang, "menu_stars"), callback_data="menu:stars")
    b.button(text=t(lang, "menu_premium"), callback_data="menu:premium")
    b.button(text=t(lang, "menu_simple_gift"), callback_data="menu:simple_gift")
    b.button(text=t(lang, "menu_nft_rent"), callback_data="menu:nft_rent")
    b.button(text=t(lang, "menu_my_orders"), callback_data="menu:my_orders")
    b.adjust(1)
    return b.as_markup()


def stars_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, pkg in enumerate(get_stars_packages()):
        b.button(
            text=f"⭐ {pkg['amount']} — {format_uzs(pkg['price_uzs'])}",
            callback_data=f"buy:stars:{i}",
        )
    b.button(text="⬅️ Назад", callback_data="menu:back")
    b.adjust(1)
    return b.as_markup()


def premium_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, pkg in enumerate(get_premium_packages()):
        b.button(
            text=f"💎 {pkg['label']} — {format_uzs(pkg['price_uzs'])}",
            callback_data=f"buy:premium:{i}",
        )
    b.button(text="⬅️ Назад", callback_data="menu:back")
    b.adjust(1)
    return b.as_markup()


def nft_rent_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, item in enumerate(get_nft_rent_items()):
        b.button(
            text=f"🖼 {item['name']} — от {format_uzs(item['base_price_per_day_uzs'])}/день",
            callback_data=f"buy:nft_rent:{i}",
        )
    b.button(text="⬅️ Назад", callback_data="menu:back")
    b.adjust(1)
    return b.as_markup()


def confirm_order_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data="order:confirm")
    b.button(text="❌ Отмена", callback_data="order:cancel")
    b.adjust(2)
    return b.as_markup()


def payment_methods_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 Оплатить и прислать чек", callback_data="pay:manual")
    b.button(text="❌ Отмена", callback_data="order:cancel")
    b.adjust(1)
    return b.as_markup()
