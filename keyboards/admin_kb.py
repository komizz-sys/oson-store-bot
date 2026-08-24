from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_review_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Оплата подтверждена", callback_data=f"admin:approve:{order_id}")
    b.button(text="❌ Отклонить", callback_data=f"admin:reject:{order_id}")
    b.adjust(1)
    return b.as_markup()


def admin_fulfill_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📤 Заказ выполнен (звёзды/подарок отправлены)", callback_data=f"admin:done:{order_id}")
    b.adjust(1)
    return b.as_markup()
