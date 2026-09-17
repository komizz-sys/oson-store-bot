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
    b.button(text="🚫 Отменить заказ", callback_data=f"admin:cancel:{order_id}")
    b.adjust(1)
    return b.as_markup()


def admin_cancel_kb(order_id: int) -> InlineKeyboardMarkup:
    """
    Одна кнопка отмены — вешается на сообщения, где заказ уже оплачен, но
    что-то пошло не так (автопокупка не удалась, фейковый чек подтвердили по
    ошибке). Без неё такой заказ навсегда висел бы у клиента в витрине как
    активный и не давал бы оформить новый.
    """
    b = InlineKeyboardBuilder()
    b.button(text="🚫 Отменить заказ", callback_data=f"admin:cancel:{order_id}")
    b.adjust(1)
    return b.as_markup()


def admin_rent_retry_kb(order_id: int) -> InlineKeyboardMarkup:
    """
    Аренду не удалось подключить — обычно потому, что ton://-перевод ещё не
    подтверждён в кошельке. Кнопка позволяет повторить попытку сразу после
    оплаты, не дожидаясь следующего автоматического повтора.
    """
    b = InlineKeyboardBuilder()
    b.button(text="🔗 Подключить сейчас", callback_data=f"admin:rentconnect:{order_id}")
    b.button(text="🚫 Отменить заказ", callback_data=f"admin:cancel:{order_id}")
    b.adjust(1)
    return b.as_markup()


def admin_cancel_cart_kb(cart_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚫 Отменить всю корзину", callback_data=f"admin:cancel_cart:{cart_id}")
    b.adjust(1)
    return b.as_markup()


def admin_cancel_request_kb(order_id: int, cart_id: str | None = None) -> InlineKeyboardMarkup:
    """
    Клиент попросил отменить УЖЕ ОПЛАЧЕННЫЙ заказ прямо из витрины.
    Сам он такой заказ отменить не может (деньги уже у продавца), поэтому
    решение принимает админ: отменить или оставить в работе.
    """
    b = InlineKeyboardBuilder()
    if cart_id:
        b.button(text="🚫 Отменить всю корзину", callback_data=f"admin:cancel_cart:{cart_id}")
    else:
        b.button(text="🚫 Отменить заказ", callback_data=f"admin:cancel:{order_id}")
    b.button(text="↩️ Оставить в работе", callback_data=f"admin:keep:{order_id}")
    b.adjust(1)
    return b.as_markup()
