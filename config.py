import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8968823813:AAHCFwCGLwR2lpi5x35UO2ng2PeW2LXfvqY")

# ID админов через запятую в .env: ADMIN_IDS=111111,222222
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "7942588812").split(",") if x.strip()]

# Реквизиты для ручной оплаты (Click/Payme/карта) — показываются пользователю
PAYMENT_CARD_NUMBER = os.getenv("PAYMENT_CARD_NUMBER", "5614684706462726")
PAYMENT_CARD_HOLDER = os.getenv("PAYMENT_CARD_HOLDER", "Komiljon Nabiyev")
PAYMENT_CLICK_LINK = os.getenv("PAYMENT_CLICK_LINK", "")
PAYMENT_PAYME_LINK = os.getenv("PAYMENT_PAYME_LINK", "")

# TON-кошелёк для автоматизации больше не хранится в .env — бот готовит
# транзакции через API MarketApp, а подписывает их админ вручную в своём
# кошельке (Tonkeeper и т.п.) по ссылке, которую присылает бот.

DB_PATH = os.getenv("DB_PATH", "data/shop.db")

CURRENCY = "UZS"

# ---- Аренда NFT-подарков через MarketApp ----
MARKETAPP_API_KEY = os.getenv("MARKETAPP_API_KEY", "877251-542c2c59028006c3fb808f6bb264a3b9-1787499671")

# Наценка на базовую цену аренды (в долях), см. services/marketapp_service.py
RENT_MARKUP = float(os.getenv("RENT_MARKUP", "1.2"))  # +20%

# Курс: сколько сум стоит 1 грамм TON (обнови при изменении курса)
TON_GRAM_RATE_UZS = int(os.getenv("TON_GRAM_RATE_UZS", "12000"))

# Комиссия за сделку аренды — в граммах TON, и какой % возвращается арендатору
RENT_FEE_GRAM = float(os.getenv("RENT_FEE_GRAM", "0.1"))
RENT_FEE_REFUND_PERCENT = int(os.getenv("RENT_FEE_REFUND_PERCENT", "40"))

# ---- Простые подарки (мишка/сердце/коробка и т.д.) ----
# Цена = кол-во звёзд подарка * этот коэффициент (сум за 1 звезду, с наценкой 20%)
STAR_UNIT_PRICE_UZS = float(os.getenv("STAR_UNIT_PRICE_UZS", "216.0"))

# ---- Мини-апп ----
# URL веб-версии магазина (адрес второго сервиса на Railway, после деплоя webapp_server.py)
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
