from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_review_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Оплата подтверждена", callback_data=f"admin:approve:{order_id}")
    b.button(text="❌ Отклонить", callback_data=f"admin:reject:{order_id}")
    b.adjust(1)
    return b.as_markup()


def admin_review_cart_kb(cart_id: str) -> InlineKeyboardMarkup:
    """Корзина оплачивается одной суммой, поэтому и подтверждается целиком —
    одна кнопка на все товары, а не по кнопке на каждый."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Оплата подтверждена (вся корзина)", callback_data=f"admin:approve_cart:{cart_id}")
    b.button(text="❌ Отклонить корзину", callback_data=f"admin:reject_cart:{cart_id}")
    b.adjust(1)
    return b.as_markup()


def admin_fulfill_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📤 Заказ выполнен (звёзды/подарок отправлены)", callback_data=f"admin:done:{order_id}")
    b.adjust(1)
    return b.as_markup()
