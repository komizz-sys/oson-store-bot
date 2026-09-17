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
            "👋 Assalomu alaykum, {name}!\n\n"
            "<blockquote>"
            "<tg-emoji emoji-id='5375583215157280942'>⭐️</tg-emoji> <b>Telegram Stars</b> — tez va arzon\n"
            "<tg-emoji emoji-id='5375333763456729352'>💎</tg-emoji> <b>Telegram Premium</b> — maxsus imkoniyatlar\n"
            "🎁 <b>Sovg'alar</b> — do'stlar va yaqinlar uchun\n"
            "<tg-emoji emoji-id='5150158575271674966'>🖼</tg-emoji> <b>NFT ijarasi</b> — profilingiz uchun noyob sovg'alar\n"
            "<tg-emoji emoji-id='5375465730621869144'>💬</tg-emoji> <b>Operator</b> — /operator, 24/7 yordam"
            "</blockquote>\n"
            "<tg-emoji emoji-id='5280946368158933554'>🛍</tg-emoji> To'lov so'mda 🇺🇿\n\n"
            "Bo'limni tanlang:"
        ),
        "menu_webapp": "🛍 Do'konni ochish",
        "menu_stars": "⭐ Stars sotib olish",
        "menu_premium": "💎 Telegram Premium",
        "menu_simple_gift": "🎁 Oddiy sovg'alar",
        "menu_nft_rent": "🖼 NFT-sovg'a ijarasi",
        "menu_my_orders": "📦 Buyurtmalarim",
        "menu_change_language": "🌐 Tilni o'zgartirish",
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
        "operator_card": (
            "<tg-emoji emoji-id='5375465730621869144'>💬</tg-emoji> <b>Operator bilan bog'lanish</b>\n\n"
            "Savol, muammo yoki buyurtma bo'yicha yordam kerakmi? "
            "Operatorimiz yozing — tez orada javob beramiz.\n\n"
            "\u2709\ufe0f {operator}"
        ),
        "operator_missing": "Hozircha operator ko'rsatilmagan. Iltimos, keyinroq urinib ko'ring.",
        "no_username_error": (
            "Sizda public username yo'q — Telegram sozlamalaridan o'rnating "
            "yoki boshqa @username ko'rsating."
        ),
        "stars_limit_error": (
            "⚠️ Bitta buyurtmada {min_stars} dan {max_stars} tagacha yulduz "
            "sotib olish mumkin. Miqdorni o'zgartirib, qayta urinib ko'ring."
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
        "order_cancelled_by_admin": (
            "🚫 Buyurtma #{order_id} sotuvchi tomonidan bekor qilindi.\n"
            "Agar pul yechilgan bo'lsa — operatorga yozing, qaytarib beramiz."
        ),
        "cart_cancelled_by_admin": (
            "🚫 Savatdagi buyurtmalar sotuvchi tomonidan bekor qilindi.\n"
            "Agar pul yechilgan bo'lsa — operatorga yozing, qaytarib beramiz."
        ),
        "order_cancel_requested": (
            "📨 Buyurtma #{order_id} ni bekor qilish so'rovi yuborildi.\n"
            "Operator tez orada ko'rib chiqadi."
        ),
        "order_cancel_kept": (
            "ℹ️ Buyurtma #{order_id} bekor qilinmadi — u hali bajarilmoqda.\n"
            "Savollaringiz bo'lsa operatorga yozing."
        ),
        "order_check_title": "Buyurtmani tekshiring:",
        "order_check_item": "Mahsulot",
        "order_check_recipient": "Qabul qiluvchi",
        "order_check_note": "Izoh",
        "order_check_fee": "Tarmoq komissiyasi",
        "order_check_fee_refund": "ijara tugagach qaytariladi",
        "order_check_total": "To'lov summasi",
        "order_check_confirm": "Hammasi to'g'rimi?",
        "order_created": "✅ #{order_id} raqamli buyurtma <b>{price}</b> summasiga yaratildi.\n\n",
        "order_pay_card": "Summani kartaga o'tkazing:\n",
        "order_pay_receiver": "Qabul qiluvchi",
        "order_pay_hint": "\nTo'lovdan so'ng shu yerga skrinshot/chek yuboring — buyurtma admin tekshiruviga o'tadi.",
        "order_pay_hint_webapp": "\nChekni do'kon oynasida yuklang (u yerda buyurtma holati jonli ko'rinadi) yoki shu yerga yuboring.",
        "pay_commission_note": "\n\n⚠️ <b>Muhim:</b> agar bankingiz o'tkazma uchun komissiya olsa, uni summa USTIGA qo'shing — kartaga aynan yuqoridagi summa tushishi kerak. Aks holda to'lov avtomatik tasdiqlanmaydi va buyurtma qo'lda tekshirishni kutadi.",
        "payment_confirmed": "✅ Buyurtma #{order_id} bo'yicha to'lov tasdiqlandi! Bajarishga kirishyapmiz.",
        "cart_check_title": "Savatingizni tekshiring:",
        "cart_created_title": "Savat buyurtmasi yaratildi",
        "cart_cancelled": "🛒 Savat bekor qilindi. Qaytadan boshlash uchun /start.",
        "cart_exact_amount": "Aynan shu summani o'tkazing:",
        "cart_payment_confirmed": "✅ To'lov tasdiqlandi! Savatdagi {count} ta mahsulot bajarilmoqda:",
        "cart_rejected": "❌ Savat bo'yicha to'lov tasdiqlanmadi. Operatorga yozing yoki qayta urinib ko'ring.",
        "rent_extended": "✅ <b>{item_name}</b> ijarasi {days} kunga uzaytirildi! Sovg'a profilingizda qoladi — hech narsa qilish shart emas.",
        "rent_extend_not_found": "Bu sovg'a bo'yicha aktiv ijara topilmadi. Do'konni qaytadan oching.",
        "rent_extend_until": "Ijara tugashi",
    },
    "ru": {
        "choose_language": "Выберите язык:",
        "welcome": (
            "👋 Здравствуйте, {name}!\n\n"
            "<blockquote>"
            "<tg-emoji emoji-id='5375583215157280942'>⭐️</tg-emoji> <b>Telegram Stars</b> — быстро и выгодно\n"
            "<tg-emoji emoji-id='5375333763456729352'>💎</tg-emoji> <b>Telegram Premium</b> — все возможности\n"
            "🎁 <b>Подарки</b> — друзьям и близким\n"
            "<tg-emoji emoji-id='5150158575271674966'>🖼</tg-emoji> <b>Аренда NFT</b> — редкие подарки для профиля\n"
            "<tg-emoji emoji-id='5375465730621869144'>💬</tg-emoji> <b>Оператор</b> — /operator, помощь 24/7"
            "</blockquote>\n"
            "<tg-emoji emoji-id='5280946368158933554'>🛍</tg-emoji> Оплата в сумах 🇺🇿\n\n"
            "Выберите раздел:"
        ),
        "menu_webapp": "🛍 Открыть магазин",
        "menu_stars": "⭐ Купить звёзды",
        "menu_premium": "💎 Telegram Premium",
        "menu_simple_gift": "🎁 Простые подарки",
        "menu_nft_rent": "🖼 Аренда NFT-подарков",
        "menu_my_orders": "📦 Мои заказы",
        "menu_change_language": "🌐 Сменить язык",
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
        "operator_card": (
            "<tg-emoji emoji-id='5375465730621869144'>💬</tg-emoji> <b>Связаться с оператором</b>\n\n"
            "Есть вопрос, проблема или нужна помощь по заказу? "
            "Напишите нашему оператору — ответим быстро.\n\n"
            "\u2709\ufe0f {operator}"
        ),
        "operator_missing": "Оператор пока не указан. Попробуйте чуть позже.",
        "no_username_error": (
            "У вас нет публичного username — установите в настройках Telegram "
            "или укажите другой @username."
        ),
        "stars_limit_error": (
            "⚠️ За один заказ можно купить от {min_stars} до {max_stars} звёзд. "
            "Измените количество и попробуйте снова."
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
        "order_cancelled_by_admin": (
            "🚫 Заказ #{order_id} отменён продавцом.\n"
            "Если деньги были списаны — напишите оператору, вернём."
        ),
        "cart_cancelled_by_admin": (
            "🚫 Заказы из корзины отменены продавцом.\n"
            "Если деньги были списаны — напишите оператору, вернём."
        ),
        "order_cancel_requested": (
            "📨 Запрос на отмену заказа #{order_id} отправлен.\n"
            "Оператор скоро его рассмотрит."
        ),
        "order_cancel_kept": (
            "ℹ️ Заказ #{order_id} не отменён — он ещё выполняется.\n"
            "Если есть вопросы, напишите оператору."
        ),
        "order_check_title": "Проверьте заказ:",
        "order_check_item": "Товар",
        "order_check_recipient": "Получатель",
        "order_check_note": "Заметка",
        "order_check_fee": "Комиссия сети",
        "order_check_fee_refund": "вернётся вам после аренды",
        "order_check_total": "Сумма к оплате",
        "order_check_confirm": "Всё верно?",
        "order_created": "✅ Заказ #{order_id} создан на сумму <b>{price}</b>.\n\n",
        "order_pay_card": "Переведите сумму на карту:\n",
        "order_pay_receiver": "Получатель",
        "order_pay_hint": "\nПосле оплаты пришлите сюда скриншот/чек — заказ уйдёт на проверку админу.",
        "order_pay_hint_webapp": "\nЧек загрузите прямо в магазине (там же виден живой статус заказа) или пришлите сюда.",
        "pay_commission_note": "\n\n⚠️ <b>Важно:</b> если ваш банк берёт комиссию за перевод — добавьте её СВЕРХУ. На карту должна прийти ровно указанная выше сумма, иначе оплата не подтвердится автоматически и заказ будет ждать ручной проверки.",
        "payment_confirmed": "✅ Оплата по заказу #{order_id} подтверждена! Приступаем к выполнению.",
        "cart_check_title": "Проверьте корзину:",
        "cart_created_title": "Заказ по корзине создан",
        "cart_cancelled": "🛒 Корзина отменена. Наберите /start, чтобы начать заново.",
        "cart_exact_amount": "Переведите ровно эту сумму:",
        "cart_payment_confirmed": "✅ Оплата подтверждена! Выполняем {count} товар(ов) из корзины:",
        "cart_rejected": "❌ Оплата по корзине не подтверждена. Напишите оператору или попробуйте ещё раз.",
        "rent_extended": "✅ Аренда <b>{item_name}</b> продлена на {days} дн.! Подарок остаётся в вашем профиле — делать ничего не нужно.",
        "rent_extend_not_found": "Активная аренда по этому подарку не найдена. Откройте магазин заново.",
        "rent_extend_until": "Аренда до",
    },
    "en": {
        "choose_language": "Choose language:",
        "welcome": (
            "👋 Welcome, {name}!\n\n"
            "<blockquote>"
            "<tg-emoji emoji-id='5375583215157280942'>⭐️</tg-emoji> <b>Telegram Stars</b> — fast and cheap\n"
            "<tg-emoji emoji-id='5375333763456729352'>💎</tg-emoji> <b>Telegram Premium</b> — all the perks\n"
            "🎁 <b>Gifts</b> — for friends and loved ones\n"
            "<tg-emoji emoji-id='5150158575271674966'>🖼</tg-emoji> <b>NFT rental</b> — rare gifts for your profile\n"
            "<tg-emoji emoji-id='5375465730621869144'>💬</tg-emoji> <b>Operator</b> — /operator, 24/7 support"
            "</blockquote>\n"
            "<tg-emoji emoji-id='5280946368158933554'>🛍</tg-emoji> Payment in Uzbek som 🇺🇿\n\n"
            "Choose a section:"
        ),
        "menu_webapp": "🛍 Open shop",
        "menu_stars": "⭐ Buy Stars",
        "menu_premium": "💎 Telegram Premium",
        "menu_simple_gift": "🎁 Simple gifts",
        "menu_nft_rent": "🖼 NFT gift rental",
        "menu_my_orders": "📦 My orders",
        "menu_change_language": "🌐 Change language",
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
        "operator_card": (
            "<tg-emoji emoji-id='5375465730621869144'>💬</tg-emoji> <b>Contact the operator</b>\n\n"
            "Got a question, an issue, or need help with an order? "
            "Message our operator — we reply fast.\n\n"
            "\u2709\ufe0f {operator}"
        ),
        "operator_missing": "No operator is set right now. Please try again later.",
        "no_username_error": (
            "You don't have a public username — set one in Telegram settings "
            "or specify a different @username."
        ),
        "stars_limit_error": (
            "⚠️ You can buy between {min_stars} and {max_stars} stars per order. "
            "Change the amount and try again."
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
        "order_cancelled_by_admin": (
            "🚫 Order #{order_id} was cancelled by the seller.\n"
            "If you were charged — contact the operator and we'll refund you."
        ),
        "cart_cancelled_by_admin": (
            "🚫 The orders in your cart were cancelled by the seller.\n"
            "If you were charged — contact the operator and we'll refund you."
        ),
        "order_cancel_requested": (
            "📨 A cancellation request for order #{order_id} has been sent.\n"
            "The operator will review it shortly."
        ),
        "order_cancel_kept": (
            "ℹ️ Order #{order_id} was not cancelled — it's still being fulfilled.\n"
            "If you have questions, contact the operator."
        ),
        "order_check_title": "Check your order:",
        "order_check_item": "Item",
        "order_check_recipient": "Recipient",
        "order_check_note": "Note",
        "order_check_fee": "Network fee",
        "order_check_fee_refund": "refunded after the rental ends",
        "order_check_total": "Total to pay",
        "order_check_confirm": "Is everything correct?",
        "order_created": "✅ Order #{order_id} created for <b>{price}</b>.\n\n",
        "order_pay_card": "Transfer the amount to the card:\n",
        "order_pay_receiver": "Recipient",
        "order_pay_hint": "\nAfter payment, send the receipt screenshot here — the order goes to admin review.",
        "order_pay_hint_webapp": "\nUpload the receipt right in the shop (it shows live order status) or send it here.",
        "pay_commission_note": "\n\n⚠️ <b>Important:</b> if your bank charges a transfer fee, add it ON TOP — exactly the amount above must arrive on the card, otherwise the payment won't be confirmed automatically and the order will wait for a manual check.",
        "payment_confirmed": "✅ Payment for order #{order_id} confirmed! We're starting fulfillment.",
        "cart_check_title": "Check your cart:",
        "cart_created_title": "Cart order created",
        "cart_cancelled": "🛒 Cart cancelled. Type /start to begin again.",
        "cart_exact_amount": "Transfer exactly this amount:",
        "cart_payment_confirmed": "✅ Payment confirmed! Fulfilling {count} item(s) from your cart:",
        "cart_rejected": "❌ The cart payment was not confirmed. Contact the operator or try again.",
        "rent_extended": "✅ The rental of <b>{item_name}</b> has been extended by {days} day(s)! The gift stays on your profile — nothing to do.",
        "rent_extend_not_found": "No active rental found for this gift. Please reopen the shop.",
        "rent_extend_until": "Rented until",
    },
}


def t(lang: str | None, key: str) -> str:
    lang = lang if lang in TRANSLATIONS else "ru"
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["ru"].get(key, key))
