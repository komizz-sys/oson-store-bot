"""
Переводы для бота. Полностью переведены главные экраны (старт, меню, каталог,
статусы заказов) — этого достаточно, чтобы пользователь мог выбрать язык и
пользоваться магазином. Шаги оформления заказа (ввод получателя, подтверждение,
загрузка чека) пока на русском для всех языков — это следующий шаг, если нужно
дальше расширять перевод.

Языки: узбекский, русский, английский (полные переводы). Казахский/таджикский
убраны из выбора по решению владельца бота.
"""

LANGUAGES = [
    ("uz", "🇺🇿", "O'zbek"),
    ("ru", "🇷🇺", "Русский"),
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
        "no_username_error": (
            "Sizda public username yo'q — Telegram sozlamalaridan o'rnating "
            "yoki boshqa @username ko'rsating."
        ),
        "proof_received": (
            "✅ Chek qabul qilindi! Buyurtmangiz admin tomonidan tekshirilmoqda.\n\n"
            "⏳ <b>Sizning buyurtmangiz bajarilyabdi, iltimos kutib turing</b> — "
            "o'rtacha buyurtmalar 3-10 daqiqada bajariladi."
        ),
        "order_completed": (
            "🎉 <b>Buyurtma #{order_id} ({item_name}) bajarildi!</b>\n"
            "Xaridingiz uchun rahmat 🙌\n\n"
            "Sizni yana kutib qolamiz! 🤗"
        ),
        "order_rejected": (
            "❌ Buyurtma #{order_id} bo'yicha to'lov tasdiqlanmadi.\n"
            "Xato deb hisoblasangiz — operator bilan bog'laning."
        ),
        "payment_confirmed": "✅ Buyurtma #{order_id} bo'yicha to'lov tasdiqlandi! Bajarishga kirishyapmiz.",
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
        "no_username_error": (
            "У вас нет публичного username — установите в настройках Telegram "
            "или укажите другой @username."
        ),
        "proof_received": (
            "✅ Чек получен! Заказ отправлен на проверку админу.\n\n"
            "⏳ <b>Ваш заказ выполняется, пожалуйста подождите</b> — "
            "в среднем заказы выполняются за 3-10 минут."
        ),
        "order_completed": (
            "🎉 <b>Заказ #{order_id} ({item_name}) выполнен!</b>\n"
            "Спасибо за покупку 🙌\n\n"
            "Ждём вас снова! 🤗"
        ),
        "order_rejected": (
            "❌ Оплата по заказу #{order_id} не подтверждена.\n"
            "Если считаете это ошибкой — напишите оператору."
        ),
        "payment_confirmed": "✅ Оплата по заказу #{order_id} подтверждена! Приступаем к выполнению.",
    },
    "en": {
        "choose_language": "Choose language:",
        "welcome": (
            "👋 Welcome!\n\n"
            "Here you can buy ⭐ Telegram Stars, 💎 Telegram Premium "
            "and rent 🖼 NFT gifts. Payment in Uzbek som.\n\n"
            "Choose a section:"
        ),
        "menu_webapp": "🛍 Open shop",
        "menu_stars": "⭐ Buy Stars",
        "menu_premium": "💎 Telegram Premium",
        "menu_simple_gift": "🎁 Simple gifts",
        "menu_nft_rent": "🖼 NFT gift rental",
        "menu_my_orders": "📦 My orders",
        "back": "⬅️ Back",
        "stars_header": "⭐ Choose a Stars package:",
        "premium_header": "💎 Choose Telegram Premium duration:",
        "my_orders_empty": "You don't have any orders yet.",
        "my_orders_header": "📦 <b>Your recent orders:</b>\n",
        "status_awaiting_payment": "⏳ Awaiting payment",
        "status_payment_review": "🔍 Payment under review",
        "status_paid": "✅ Paid, preparing order",
        "status_fulfilling": "🚚 In progress",
        "status_completed": "🎉 Completed",
        "status_rejected": "❌ Rejected",
        "language_changed": "Language changed ✅",
        "sub_required_text": "📢 To use the bot, please subscribe to our channel first:",
        "sub_button": "📢 Go to channel",
        "sub_check_button": "✅ I'm subscribed",
        "sub_still_not": "You're not subscribed yet. Please join the channel first.",
        "support_prompt": "💬 Write your message — an operator will reply soon:",
        "support_sent": "✅ Message sent. An operator will reply soon.",
        "menu_support": "💬 Support / Operator",
        "no_username_error": (
            "You don't have a public username — set one in Telegram settings "
            "or specify a different @username."
        ),
        "proof_received": (
            "✅ Receipt received! Your order was sent to the admin for review.\n\n"
            "⏳ <b>Your order is being processed, please wait</b> — "
            "orders are usually completed within 3-10 minutes."
        ),
        "order_completed": (
            "🎉 <b>Order #{order_id} ({item_name}) completed!</b>\n"
            "Thanks for your purchase 🙌\n\n"
            "We'll be waiting for you again! 🤗"
        ),
        "order_rejected": (
            "❌ Payment for order #{order_id} was not confirmed.\n"
            "If you think this is a mistake — contact the operator."
        ),
        "payment_confirmed": "✅ Payment for order #{order_id} confirmed! We're starting fulfillment.",
    },
}


def t(lang: str | None, key: str) -> str:
    lang = lang if lang in TRANSLATIONS else "ru"
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["ru"].get(key, key))
