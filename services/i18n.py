"""
Переводы для бота. Полностью переведены главные экраны (старт, меню, каталог,
статусы заказов) — этого достаточно, чтобы пользователь мог выбрать язык и
пользоваться магазином. Шаги оформления заказа (ввод получателя, подтверждение,
загрузка чека) пока на русском для всех языков — это следующий шаг, если нужно
дальше расширять перевод.

kk/tj/en временно используют русские тексты (алиас) — отдельных переводов под
них пока нет.
"""

LANGUAGES = [
    ("uz", "🇺🇿", "O'zbek"),
    ("ru", "🇷🇺", "Русский"),
    ("kk", "🇰🇿", "Қазақ"),
    ("tj", "🇹🇯", "Тоҷик"),
    ("en", "🇬🇧", "English"),
]

TRANSLATIONS = {
    "uz": {
        "choose_language": "Tilni tanlang:",
        "welcome": (
            "👋 Xush kelibsiz!\n\n"
            "Bu yerda ⭐ Telegram Stars, 💎 Telegram Premium sotib olishingiz "
            "va 🖼 NFT-sovg'alarni ijaraga olishingiz mumkin. To'lov so'mda.\n\n"
            "Bo'limni tanlang:"
        ),
        "menu_webapp": "🛍 Do'konni ochish",
        "menu_stars": "⭐ Stars sotib olish",
        "menu_premium": "💎 Telegram Premium",
        "menu_simple_gift": "🎁 Oddiy sovg'alar",
        "menu_nft_rent": "🖼 NFT-sovg'a ijarasi",
        "menu_my_orders": "📦 Buyurtmalarim",
        "back": "⬅️ Orqaga",
        "stars_header": "⭐ Stars to'plamini tanlang:",
        "premium_header": "💎 Telegram Premium muddatini tanlang:",
        "my_orders_empty": "Sizda hali buyurtmalar yo'q.",
        "my_orders_header": "📦 <b>Oxirgi buyurtmalaringiz:</b>\n",
        "status_awaiting_payment": "⏳ To'lov kutilmoqda",
        "status_payment_review": "🔍 To'lov tekshirilmoqda",
        "status_paid": "✅ To'landi, tayyorlanmoqda",
        "status_fulfilling": "🚚 Bajarilmoqda",
        "status_completed": "🎉 Bajarildi",
        "status_rejected": "❌ Rad etildi",
        "language_changed": "Til o'zgartirildi ✅",
        "sub_required_text": "📢 Botdan foydalanish uchun avval kanalimizga a'zo bo'ling:",
        "sub_button": "📢 Kanalga o'tish",
        "sub_check_button": "✅ A'zo bo'ldim",
        "sub_still_not": "Hali a'zo bo'lmagansiz. Avval kanalga o'ting.",
        "support_prompt": "💬 Xabaringizni yozing — operator tez orada javob beradi:",
        "support_sent": "✅ Xabaringiz yuborildi. Operator tez orada javob beradi.",
        "menu_support": "💬 Yordam / Operator",
    },
    "ru": {
        "choose_language": "Выберите язык:",
        "welcome": (
            "👋 Добро пожаловать!\n\n"
            "Здесь можно купить ⭐ Telegram Stars, 💎 Telegram Premium "
            "и арендовать 🖼 NFT-подарки. Оплата в узбекских сумах.\n\n"
            "Выберите раздел:"
        ),
        "menu_webapp": "🛍 Открыть магазин",
        "menu_stars": "⭐ Купить звёзды",
        "menu_premium": "💎 Telegram Premium",
        "menu_simple_gift": "🎁 Простые подарки",
        "menu_nft_rent": "🖼 Аренда NFT-подарков",
        "menu_my_orders": "📦 Мои заказы",
        "back": "⬅️ Назад",
        "stars_header": "⭐ Выберите пакет звёзд:",
        "premium_header": "💎 Выберите срок Telegram Premium:",
        "my_orders_empty": "У вас пока нет заказов.",
        "my_orders_header": "📦 <b>Ваши последние заказы:</b>\n",
        "status_awaiting_payment": "⏳ Ожидает оплаты",
        "status_payment_review": "🔍 Оплата на проверке",
        "status_paid": "✅ Оплачено, готовим заказ",
        "status_fulfilling": "🚚 Выполняется",
        "status_completed": "🎉 Выполнен",
        "status_rejected": "❌ Отклонён",
        "language_changed": "Язык изменён ✅",
        "sub_required_text": "📢 Чтобы пользоваться ботом, сначала подпишитесь на наш канал:",
        "sub_button": "📢 Перейти в канал",
        "sub_check_button": "✅ Я подписался",
        "sub_still_not": "Вы ещё не подписаны. Сначала перейдите в канал.",
        "support_prompt": "💬 Напишите ваше сообщение — оператор скоро ответит:",
        "support_sent": "✅ Сообщение отправлено. Оператор скоро ответит.",
        "menu_support": "💬 Поддержка / Оператор",
    },
}
TRANSLATIONS["kk"] = TRANSLATIONS["ru"]
TRANSLATIONS["tj"] = TRANSLATIONS["ru"]
TRANSLATIONS["en"] = TRANSLATIONS["ru"]


def t(lang: str | None, key: str) -> str:
    lang = lang if lang in TRANSLATIONS else "ru"
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["ru"].get(key, key))
