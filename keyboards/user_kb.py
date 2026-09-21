from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from services.prices import get_stars_packages, get_premium_packages, get_nft_rent_items, format_uzs
from services.i18n import t, LANGUAGES
from services.subscription import channel_link


def language_select_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, flag, name in LANGUAGES:
        b.button(text=f"{flag} {name}", callback_data=f"setlang:{code}")
    b.adjust(1)
    return b.as_markup()


# УБРАНО: кнопка магазина на клавиатуре чата (ReplyKeyboardMarkup).
#
# Она открывала витрину по СТАРОМУ пути — через sendData(): витрина закрывалась,
# бот присылал в чат «Buyurtmani tekshiring… Подтвердить / Отмена», и покупку
# приходилось подтверждать заново уже в переписке. Кнопок «открыть магазин»
# было две (эта и в самом меню /start), они вели себя по-разному, и человек
# не понимал, почему заказ то оформляется сразу, то спрашивает ещё раз.
#
# Осталась одна кнопка — в меню /start (main_menu_kb): она открывает витрину
# как обычный мини-апп, и заказ уходит на сервер напрямую.
#
# Старую клавиатуру нужно ещё и СНЯТЬ с телефонов тех, у кого она уже
# показана — этим занимается drop_reply_kb() в handlers/user.py.


def subscribe_gate_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    link = channel_link()
    if link:
        b.button(text=t(lang, "sub_button"), url=link)
    b.button(text=t(lang, "sub_check_button"), callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()


def main_menu_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    """
    Главное меню: ОДИН вход в покупку — витрина.

    Раньше здесь же лежали «Stars», «Premium», «Подарки», «Аренда» и
    «Мои заказы», и получалось два независимых пути оформления: в чате и в
    мини-аппе. Люди проходили оба — выбирали товар в чате, потом открывали
    витрину и выбирали ещё раз. На выходе два заказа на одну покупку, два
    скриншота одного платежа и разбор этого вручную.
    Теперь покупка живёт только в витрине, а в чате остаётся то, чего в
    витрине нет: оператор и смена языка.

    Обработчики разделов (menu:stars и остальные) намеренно НЕ удалены: на
    них ещё могут прийти нажатия со старых сообщений, висящих у клиентов в
    переписке. Просто новых кнопок больше не появляется.
    """
    b = InlineKeyboardBuilder()
    if config.WEBAPP_URL:
        b.button(text=t(lang, "menu_webapp"), web_app=WebAppInfo(url=config.WEBAPP_URL))
    b.button(text=t(lang, "menu_support"), callback_data="menu:support")
    b.button(text=t(lang, "menu_change_language"), callback_data="menu:change_language")
    # Витрина — во всю ширину сверху, под ней оператор и язык в один ряд.
    if config.WEBAPP_URL:
        b.adjust(1, 2)
    else:
        b.adjust(2)
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


def confirm_cart_kb() -> InlineKeyboardMarkup:
    """Подтверждение корзины — отдельные callback'и, чтобы не пересекаться с
    подтверждением одиночного заказа (у него своё состояние и свой обработчик)."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data="cart:confirm")
    b.button(text="❌ Отмена", callback_data="cart:cancel")
    b.adjust(2)
    return b.as_markup()


def payment_methods_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 Оплатить и прислать чек", callback_data="pay:manual")
    b.button(text="❌ Отмена", callback_data="order:cancel")
    b.adjust(1)
    return b.as_markup()
