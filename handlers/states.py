from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    entering_recipient = State()   # ждём @username получателя звёзд/премиум/подарка
    entering_rent_days = State()   # ждём кол-во дней аренды NFT
    confirming = State()           # финальное подтверждение перед оплатой
    confirming_cart = State()      # то же, но для корзины (несколько товаров, одна оплата)
    waiting_payment_proof = State()  # ждём скрин/чек оплаты
