const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.expand(); tg.ready(); }

/**
 * Telegram иногда отдаёт initData не мгновенно на первом кадре WebView —
 * страница уже выполнилась, а initData ещё пустая строка (особенно на
 * некоторых версиях клиента при "холодном" открытии мини-аппа). Раньше из-за
 * этого Tarix/Profil мгновенно показывали "открой в Telegram", хотя человек
 * и так был внутри Telegram. Ждём короткими попытками, прежде чем сдаться.
 */
/**
 * Telegram иногда отдаёт initData не мгновенно на первом кадре WebView —
 * страница уже выполнилась, а initData ещё пустая строка. На слабых
 * Android-устройствах (видел в логах — Redmi Note 9S "AVERAGE" performance)
 * это может занимать заметно больше 1.5 сек, особенно на медленном интернете.
 * БАГ БЫЛ ЗДЕСЬ: ждали всего 1.5 сек и сдавались — Tarix/Profil показывали
 * "открой в Telegram", хотя человек и так был внутри Telegram, просто
 * initData ещё не успела дойти. Увеличил окно ожидания и сделал его терпеливее.
 */
function waitForInitData(maxWaitMs = 4000, stepMs = 150) {
  return new Promise(function(resolve) {
    if (tg && tg.initData) { resolve(tg.initData); return; }
    let waited = 0;
    const iv = setInterval(function() {
      waited += stepMs;
      if (tg && tg.initData) { clearInterval(iv); resolve(tg.initData); }
      else if (waited >= maxWaitMs) { clearInterval(iv); resolve(tg && tg.initData ? tg.initData : ""); }
    }, stepMs);
  });
}

/**
 * Отдельное (и обычно куда более быстрое) ожидание именно initDataUnsafe.user —
 * это НЕподписанные данные, для отображения имени/аватарки в Profil подпись
 * не нужна, поэтому не блокируем это той же долгой проверкой, что my_orders/my_stats.
 */
function waitForUnsafeUser(maxWaitMs = 4000, stepMs = 150) {
  return new Promise(function(resolve) {
    const get = function() { return tg && tg.initDataUnsafe && tg.initDataUnsafe.user; };
    if (get()) { resolve(get()); return; }
    let waited = 0;
    const iv = setInterval(function() {
      waited += stepMs;
      const u = get();
      if (u) { clearInterval(iv); resolve(u); }
      else if (waited >= maxWaitMs) { clearInterval(iv); resolve(null); }
    }, stepMs);
  });
}

/* ---------------- i18n ---------------- */
const I18N = {
  uz: {
    ijara_title: "Gift Arendasi", history_title: "Xaridlar tarixi",
    history_empty: "Hozircha xaridlar tarixi bo'sh.", history_hint: "To'liq tarix - botdagi \"Mening buyurtmalarim\" bo'limida.",
    top_title: "Reyting", top_subtitle: "Eng faol mijozlar", top_forming: "Reyting shakllanmoqda", top_hint: "Birinchi xaridni amalga oshiring!",
    profile_operator: "Operator", profile_channel: "\ud83d\udce2 Bot kanali", profile_orders_channel: "\ud83d\uded2 Savdo/Orderlar",
    nav_main: "Asosiy", nav_rent: "Ijara", nav_history: "Tarix", nav_profile: "Profil",
    modal_to_whom: "Kimga?", modal_to_self: "O'zimga", modal_to_friend: "Do'stimga",
    modal_recipient_label: "Qabul qiluvchi (@username):", modal_message_label: "Xabar (ixtiyoriy):",
    modal_message_placeholder: "Tabrik matni...", modal_rent_days: "Necha kunga?", modal_gift_quantity: "Nechta dona?",
    modal_card_label: "To'lov uchun karta (Uzcard/Humo)", modal_card_holder_label: "Qabul qiluvchi",
    modal_copy: "Nusxalash", modal_paid: "To'ladim", modal_cancel: "Bekor qilish",
    err_username: "Username kiriting", err_no_username: "Sizda public username yo'q. Telegram sozlamalaridan o'rnating yoki \"Do'stimga\" tanlang.",
    rent_terms: (fee, refund) => "Xizmat haqi: ~" + fee + ". Ijara tugagach ~" + refund + " qaytariladi.",
    copied: "Nusxalandi!", empty: "Hozircha bo'sh.", rent_days_suffix: "kun", rent_from: "dan", rent_btn: "Ijaraga olish",
    modal_preview: "Telegram-da ko'rish",
    sort_recent: "Yangilari", sort_price_asc: "Narx: arzondan qimmatga", sort_price_desc: "Narx: qimmatdan arzonga",
    sort_duration_asc: "Muddat: qisqa", sort_duration_desc: "Muddat: uzun",
    load_more: "Ko'proq ko'rsatish", premium_title: "Telegram Premium olish", premium_subtitle: "O'zingiz yoki yaqiningiz uchun", premium_get_suffix: "olish",
    custom_amount: "Boshqa miqdor", custom_amount_hint: "O'zingiz kiriting", custom_amount_label: "Nechta Stars?",
    recent_recipient_label: "Yaqinda:", collection_all: "Barcha kolleksiyalar", collection_title: "Kolleksiya bo'yicha filtr",
    live_label: "JONLI", minutes_ago: "daqiqa oldin", hours_ago: "soat oldin",
    status_awaiting_payment: "To'lov kutilmoqda", status_payment_review: "Tekshirilmoqda", status_paid: "To'landi",
    status_fulfilling: "Bajarilmoqda", status_completed: "Bajarildi", status_rejected: "Bekor qilindi",
    cat_stars: "\u2b50 Stars", cat_premium: "\ud83d\udc8e Premium", cat_simple_gift: "\ud83c\udf81 Sovg'a", cat_nft_rent: "\ud83d\uddbc Ijara",
    top_period_today: "Bugun", top_period_week: "Hafta", top_period_month: "Oy", top_period_all: "Hammasi",
    top_orders_suffix: "buyurtma", top_you: "Siz", top_empty: "Bu davrda hali xaridlar yo'q.", badge_popular: "Mashhur", per_star: "so'm / yulduz", profile_no_purchases: "Birinchi xaridni amalga oshiring 🚀",
    howto_title: "🎁 Ijara qanday ishlaydi?",
    howto_steps: ["Gift va ijara muddatini tanlang", "Buyurtmani rasmiylashtiring va to'lovni amalga oshiring", "Admin to'lovni tasdiqlaydi", "Telegram botga tutorial video yuboriladi", "Videoni ko'rib, Telegram'dan shaxsiy havolangizni oling", "Havolani shu yerdagi maydonga joylang", "Havola tekshiriladi va sovg'a ulanadi", "Sovg'a profilingizda ko'rinadi ✅"],
    ao_title: "Aktiv buyurtma", ao_awaiting_payment: "To'lov kutilmoqda", ao_payment_review: "To'lov tekshirilmoqda",
    ao_paid: "To'lov tasdiqlandi", ao_fulfilling: "Bajarilmoqda",
    ao_link_title: "Keyingi qadam: havolani kiriting", ao_link_hint: "Botga yuborilgan tutorial videodagi ko'rsatma bo'yicha olingan havolani joylang.",
    ao_link_send: "Havolani yuborish", ao_watch_tutorial: "Tutorialni ko'rish (botda)",
    ao_connected: "Sovg'a profilingizga ulandi!",
    ao_err_empty: "Havolani kiriting", ao_err_bad_link: "Havola noto'g'ri. U tc:// bilan boshlanishi kerak.",
    ao_err_connect: "Ulashda xatolik. Operator tez orada qo'lda ulab beradi.", ao_err_network: "Server bilan bog'lanib bo'lmadi.", ao_cancel: "Buyurtmani bekor qilish", ao_cancel_confirm: "Buyurtma bekor qilinsinmi?", ao_pay_title: "To'lovni amalga oshiring", ao_pay_hint: "Kartaga summani o'tkazing va chek skrinshotini shu yerga yuklang.", ao_pay_upload: "Chek skrinshotini yuklash", ao_receipt_sent: "✅ Chek yuborildi! Admin tez orada tekshiradi.", ao_err_too_big: "Fayl juda katta (8 MB gacha).", ao_err_receipt: "Chekni yuborib bo'lmadi, qayta urinib ko'ring.", ao_err_wrong_status: "Bu buyurtma uchun chek allaqachon yuborilgan.", ao_err_no_image: "Rasmni o'qib bo'lmadi. Galereyadan oddiy rasm (JPG/PNG) tanlang.", ao_err_not_found: "Buyurtma topilmadi.",
    profile_stats_title: "Mening statistikam", profile_stats_rank: "Reyting o'rningiz", profile_stats_total: "Jami xarid",
    history_loading: "Yuklanmoqda...", history_open_bot: "Ochish uchun botni Telegram ichida oching.",
    order_success_title: "Buyurtma muvaffaqiyatli qabul qilindi", order_success_hint: "Tez orada tasdiqlaymiz — natija shu botda yoziladi.",
    order_success_item: "Mahsulot", order_success_recipient: "Qabul qiluvchi", order_success_total: "Summa",
    order_success_history: "Tarixni ko'rish", order_success_more: "Yana xarid qilish", order_success_home: "Asosiy sahifa",
    nav_cart: "Savat", cart_title: "Savat", cart_empty: "Savat bo'sh", cart_empty_hint: "Mahsulot tanlang va \"Savatga\" tugmasini bosing.",
    cart_add: "Savatga", cart_added: "Savatga qo'shildi ✅", cart_buy_now: "Hozir to'lash",
    cart_total: "Jami", cart_pay: "Hammasini to'lash", cart_clear: "Savatni tozalash",
    cart_clear_confirm: "Savatni tozalaymizmi?", cart_to_self: "O'zimga", cart_to: "Kimga",
    cart_items_suffix: "ta mahsulot", cart_go_shop: "Do'konga o'tish",
    cart_pay_hint: "Kartaga jami summani bitta o'tkazma bilan yuboring, so'ng \"To'ladim\" tugmasini bosing.",
    cart_err_generic: "Buyurtmani yuborib bo'lmadi, qayta urinib ko'ring.",
    cart_err_no_username: "Sizda public username yo'q. Telegram sozlamalaridan o'rnating yoki \"Do'stimga\" tanlang.",
    cart_active_title: "Savat",
    cart_success_hint: "Buyurtmani tasdiqlash uchun bot chatini oching — u yerda \"Tasdiqlash\" tugmasini bosing.",
    flow_step_created: "Qabul qilindi", flow_step_payment: "To'lov", flow_step_doing: "Bajarilmoqda", flow_step_done: "Tayyor",
    flow_awaiting_title: "To'lovni kutyapmiz", flow_awaiting_sub: "Summani kartaga o'tkazing va chek skrinshotini shu yerga yuklang — qolganini shu oynada ko'rasiz.",
    flow_review_title: "To'lov tekshirilmoqda", flow_review_sub: "Odatda bir necha daqiqa. Oyna o'zi yangilanadi — yopmasangiz ham bo'ladi.",
    flow_doing_title: "Buyurtma bajarilmoqda", flow_doing_sub: "Allaqachon ish boshladik. Tayyor bo'lishi bilan shu yerda ko'rasiz.",
    flow_done_title: "Bajarildi!", flow_done_sub: "Buyurtmangiz yakunlandi. Xaridingiz uchun rahmat 🙌",
    flow_rejected_title: "Buyurtma bekor qilindi", flow_rejected_sub: "To'lov tasdiqlanmadi. Operatorga yozing yoki qayta urinib ko'ring.",
    flow_pay_exact: "Aynan shu summani o'tkazing:",
    flow_commission_note: "Agar bankingiz o'tkazma uchun komissiya olsa — uni summa USTIGA qo'shing. Kartaga aynan shu summa tushishi kerak, aks holda to'lov avtomatik tasdiqlanmaydi.", flow_minimize: "Yopish (do'konga qaytish)", flow_write_operator: "Operatorga yozish",
    flow_tips: ["Qabul qiluvchi tekshirilmoqda…", "Buyurtma tayyorlanmoqda…", "Yetkazib berilmoqda…", "Deyarli tayyor…"],
    rentals_title: "Mening ijaralarim", rentals_empty: "Aktiv ijara yo'q.",
    rent_ends_in: "Tugashiga", rent_days_short: "kun", rent_hours_short: "soat",
    rent_extend: "Uzaytirish", rent_extend_title: "Ijarani uzaytirish", rent_extend_days: "Necha kunga uzaytiramiz?",
    rent_extend_until: "Yangi tugash sanasi", rent_extend_note: "Sovg'a profilingizda qoladi — havolani qayta yuborish shart emas.",
    rent_ending_soon: "Tez orada tugaydi!",
  },
  ru: {
    ijara_title: "Аренда гифтов", history_title: "История покупок",
    history_empty: "Пока пусто.", history_hint: "Полная история - в разделе «Мои заказы» в боте.",
    top_title: "Рейтинг", top_subtitle: "Самые активные клиенты", top_forming: "Рейтинг формируется", top_hint: "Сделайте первую покупку!",
    profile_operator: "Оператор", profile_channel: "\ud83d\udce2 Канал бота", profile_orders_channel: "\ud83d\uded2 Заказы/Отзывы",
    nav_main: "Главная", nav_rent: "Аренда", nav_history: "История", nav_profile: "Профиль",
    modal_to_whom: "Кому?", modal_to_self: "Себе", modal_to_friend: "Другу",
    modal_recipient_label: "Получатель (@username):", modal_message_label: "Сообщение (необязательно):",
    modal_message_placeholder: "Текст поздравления...", modal_rent_days: "На сколько дней?", modal_gift_quantity: "Сколько штук?",
    modal_card_label: "Карта для оплаты (Uzcard/Humo)", modal_card_holder_label: "Получатель",
    modal_copy: "Скопировать", modal_paid: "Я оплатил", modal_cancel: "Отмена",
    err_username: "Введите username", err_no_username: "У вас нет публичного username. Установите в настройках Telegram или выберите \"Другу\".",
    rent_terms: (fee, refund) => "Сервисный сбор: ~" + fee + ". После окончания аренды вернётся ~" + refund + ".",
    copied: "Скопировано!", empty: "Пока пусто.", rent_days_suffix: "дн.", rent_from: "от", rent_btn: "Арендовать",
    modal_preview: "Смотреть в Telegram",
    sort_recent: "Новинки", sort_price_asc: "Цена: по возрастанию", sort_price_desc: "Цена: по убыванию",
    sort_duration_asc: "Срок: короче", sort_duration_desc: "Срок: длиннее",
    load_more: "Показать ещё", premium_title: "Оформить Telegram Premium", premium_subtitle: "Себе или близкому человеку", premium_get_suffix: "оформить",
    custom_amount: "Другое количество", custom_amount_hint: "Введите сами", custom_amount_label: "Сколько звёзд?",
    recent_recipient_label: "Недавнее:", collection_all: "Все коллекции", collection_title: "Фильтр по коллекции",
    live_label: "СЕЙЧАС", minutes_ago: "мин назад", hours_ago: "ч назад",
    status_awaiting_payment: "Ждём оплату", status_payment_review: "Проверяется", status_paid: "Оплачено",
    status_fulfilling: "Выполняется", status_completed: "Выполнено", status_rejected: "Отменено",
    cat_stars: "\u2b50 Stars", cat_premium: "\ud83d\udc8e Premium", cat_simple_gift: "\ud83c\udf81 Подарок", cat_nft_rent: "\ud83d\uddbc Аренда",
    top_period_today: "Сегодня", top_period_week: "Неделя", top_period_month: "Месяц", top_period_all: "Всё время",
    top_orders_suffix: "заказ(ов)", top_you: "Вы", top_empty: "За этот период покупок ещё не было.", badge_popular: "Популярный", per_star: "сум / звезда", profile_no_purchases: "Сделайте первую покупку 🚀",
    howto_title: "🎁 Как работает аренда?",
    howto_steps: ["Выберите подарок и срок аренды", "Оформите заказ и оплатите", "Админ подтверждает оплату", "В Telegram-бот приходит видео-инструкция", "Посмотрите видео и получите свою персональную ссылку", "Вставьте ссылку в поле здесь", "Ссылка проверяется, подарок подключается", "Подарок появляется в вашем профиле ✅"],
    ao_title: "Активный заказ", ao_awaiting_payment: "Ждём оплату", ao_payment_review: "Проверяем оплату",
    ao_paid: "Оплата подтверждена", ao_fulfilling: "Выполняется",
    ao_link_title: "Следующий шаг: вставьте ссылку", ao_link_hint: "Вставьте ссылку, полученную по инструкции из видео, которое пришло в бот.",
    ao_link_send: "Отправить ссылку", ao_watch_tutorial: "Посмотреть инструкцию (в боте)",
    ao_connected: "Подарок подключён к профилю!",
    ao_err_empty: "Введите ссылку", ao_err_bad_link: "Неверная ссылка. Она должна начинаться с tc://",
    ao_err_connect: "Ошибка подключения. Оператор скоро подключит вручную.", ao_err_network: "Не удалось связаться с сервером.", ao_cancel: "Отменить заказ", ao_cancel_confirm: "Отменить заказ?", ao_pay_title: "Оплатите заказ", ao_pay_hint: "Переведите сумму на карту и загрузите сюда скриншот чека.", ao_pay_upload: "Загрузить скриншот чека", ao_receipt_sent: "✅ Чек отправлен! Админ скоро проверит.", ao_err_too_big: "Файл слишком большой (до 8 МБ).", ao_err_receipt: "Не удалось отправить чек, попробуйте ещё раз.", ao_err_wrong_status: "Чек по этому заказу уже отправлен.", ao_err_no_image: "Не удалось прочитать изображение. Выберите обычное фото (JPG/PNG).", ao_err_not_found: "Заказ не найден.",
    profile_stats_title: "Моя статистика", profile_stats_rank: "Ваше место в рейтинге", profile_stats_total: "Всего куплено",
    history_loading: "Загрузка...", history_open_bot: "Откройте магазин внутри Telegram, чтобы увидеть историю.",
    order_success_title: "Заказ успешно оформлен", order_success_hint: "Скоро подтвердим — результат придёт в этот же чат.",
    order_success_item: "Товар", order_success_recipient: "Получатель", order_success_total: "Сумма",
    order_success_history: "Смотреть историю", order_success_more: "Купить ещё", order_success_home: "На главную",
    nav_cart: "Корзина", cart_title: "Корзина", cart_empty: "Корзина пуста", cart_empty_hint: "Выберите товар и нажмите «В корзину».",
    cart_add: "В корзину", cart_added: "Добавлено в корзину ✅", cart_buy_now: "Оплатить сейчас",
    cart_total: "Итого", cart_pay: "Оплатить всё", cart_clear: "Очистить корзину",
    cart_clear_confirm: "Очистить корзину?", cart_to_self: "Себе", cart_to: "Кому",
    cart_items_suffix: "товар(ов)", cart_go_shop: "Перейти в магазин",
    cart_pay_hint: "Переведите на карту общую сумму одним платежом и нажмите «Я оплатил».",
    cart_err_generic: "Не удалось оформить заказ, попробуйте ещё раз.",
    cart_err_no_username: "У вас нет публичного username. Установите его в настройках Telegram или выберите «Другу».",
    cart_active_title: "Корзина",
    cart_success_hint: "Откройте чат бота и нажмите «Подтвердить» — после этого придут реквизиты и сумма.",
    flow_step_created: "Оформлен", flow_step_payment: "Оплата", flow_step_doing: "Выполняется", flow_step_done: "Готово",
    flow_awaiting_title: "Ждём оплату", flow_awaiting_sub: "Переведите сумму на карту и загрузите сюда скриншот чека — дальше всё видно в этом окне.",
    flow_review_title: "Проверяем оплату", flow_review_sub: "Обычно это пара минут. Окно обновится само — можно не закрывать.",
    flow_doing_title: "Заказ выполняется", flow_doing_sub: "Уже занимаемся вашим заказом. Как будет готово — увидите здесь.",
    flow_done_title: "Выполнено!", flow_done_sub: "Заказ выполнен. Спасибо за покупку 🙌",
    flow_rejected_title: "Заказ отменён", flow_rejected_sub: "Оплата не подтверждена. Напишите оператору или оформите заново.",
    flow_pay_exact: "Переведите ровно:",
    flow_commission_note: "Если ваш банк берёт комиссию за перевод — добавьте её СВЕРХУ. На карту должна прийти ровно эта сумма, иначе оплата не подтвердится автоматически.", flow_minimize: "Свернуть (вернуться в магазин)", flow_write_operator: "Написать оператору",
    flow_tips: ["Проверяем получателя…", "Готовим заказ…", "Отправляем…", "Почти готово…"],
    rentals_title: "Мои аренды", rentals_empty: "Активных аренд нет.",
    rent_ends_in: "Осталось", rent_days_short: "дн.", rent_hours_short: "ч",
    rent_extend: "Продлить", rent_extend_title: "Продление аренды", rent_extend_days: "На сколько дней продлить?",
    rent_extend_until: "Новая дата окончания", rent_extend_note: "Подарок остаётся в профиле — ссылку заново присылать не нужно.",
    rent_ending_soon: "Скоро закончится!",
  },
  en: {
    ijara_title: "Gift rental", history_title: "Purchase history",
    history_empty: "Nothing here yet.", history_hint: "Full history is in \"My orders\" in the bot chat.",
    top_title: "Rating", top_subtitle: "Most active customers", top_forming: "Rating is forming", top_hint: "Make your first purchase!",
    profile_operator: "Operator", profile_channel: "\ud83d\udce2 Bot channel", profile_orders_channel: "\ud83d\uded2 Orders channel",
    nav_main: "Home", nav_rent: "Rent", nav_history: "History", nav_profile: "Profile",
    modal_to_whom: "For whom?", modal_to_self: "Myself", modal_to_friend: "A friend",
    modal_recipient_label: "Recipient (@username):", modal_message_label: "Message (optional):",
    modal_message_placeholder: "Congratulation text...", modal_rent_days: "For how many days?", modal_gift_quantity: "How many?",
    modal_card_label: "Payment card (Uzcard/Humo)", modal_card_holder_label: "Recipient",
    modal_copy: "Copy", modal_paid: "I've paid", modal_cancel: "Cancel",
    err_username: "Enter a username", err_no_username: "You don't have a public username. Set one in Telegram settings or choose \"A friend\".",
    rent_terms: (fee, refund) => "Service fee: ~" + fee + ". ~" + refund + " is refunded after the rental ends.",
    copied: "Copied!", empty: "Nothing here yet.", rent_days_suffix: "days", rent_from: "from", rent_btn: "Rent",
    modal_preview: "View in Telegram",
    sort_recent: "Newest", sort_price_asc: "Price: low to high", sort_price_desc: "Price: high to low",
    sort_duration_asc: "Duration: shortest", sort_duration_desc: "Duration: longest",
    load_more: "Show more", premium_title: "Get Telegram Premium", premium_subtitle: "For yourself or someone else", premium_get_suffix: "get",
    custom_amount: "Custom amount", custom_amount_hint: "Enter your own", custom_amount_label: "How many Stars?",
    recent_recipient_label: "Recent:", collection_all: "All collections", collection_title: "Filter by collection",
    live_label: "LIVE", minutes_ago: "min ago", hours_ago: "h ago",
    status_awaiting_payment: "Awaiting payment", status_payment_review: "Under review", status_paid: "Paid",
    status_fulfilling: "In progress", status_completed: "Completed", status_rejected: "Cancelled",
    cat_stars: "\u2b50 Stars", cat_premium: "\ud83d\udc8e Premium", cat_simple_gift: "\ud83c\udf81 Gift", cat_nft_rent: "\ud83d\uddbc Rent",
    top_period_today: "Today", top_period_week: "Week", top_period_month: "Month", top_period_all: "All time",
    top_orders_suffix: "order(s)", top_you: "You", top_empty: "No purchases in this period yet.", badge_popular: "Popular", per_star: "so'm / star", profile_no_purchases: "Make your first purchase 🚀",
    howto_title: "🎁 How does renting work?",
    howto_steps: ["Pick a gift and rental period", "Place the order and pay", "Admin confirms your payment", "A tutorial video is sent to the Telegram bot", "Watch it and get your personal link from Telegram", "Paste the link into the field here", "The link is verified and the gift is connected", "The gift appears on your profile ✅"],
    ao_title: "Active order", ao_awaiting_payment: "Awaiting payment", ao_payment_review: "Checking payment",
    ao_paid: "Payment confirmed", ao_fulfilling: "In progress",
    ao_link_title: "Next step: paste your link", ao_link_hint: "Paste the link you got by following the tutorial video sent to the bot.",
    ao_link_send: "Send link", ao_watch_tutorial: "Watch tutorial (in bot)",
    ao_connected: "Gift connected to your profile!",
    ao_err_empty: "Enter the link", ao_err_bad_link: "Invalid link. It should start with tc://",
    ao_err_connect: "Connection error. An operator will connect it manually soon.", ao_err_network: "Could not reach the server.", ao_cancel: "Cancel order", ao_cancel_confirm: "Cancel this order?", ao_pay_title: "Pay for your order", ao_pay_hint: "Transfer the amount to the card and upload the receipt screenshot here.", ao_pay_upload: "Upload receipt screenshot", ao_receipt_sent: "✅ Receipt sent! The admin will check it shortly.", ao_err_too_big: "File is too large (max 8 MB).", ao_err_receipt: "Could not send the receipt, please try again.", ao_err_wrong_status: "A receipt for this order was already sent.", ao_err_no_image: "Could not read the image. Pick a regular photo (JPG/PNG).", ao_err_not_found: "Order not found.",
    profile_stats_title: "My stats", profile_stats_rank: "Your rank", profile_stats_total: "Total spent",
    history_loading: "Loading...", history_open_bot: "Open the shop inside Telegram to see your history.",
    order_success_title: "Order placed successfully", order_success_hint: "We'll confirm soon — the result will be posted in this chat.",
    order_success_item: "Item", order_success_recipient: "Recipient", order_success_total: "Total",
    order_success_history: "View history", order_success_more: "Buy more", order_success_home: "Home",
    nav_cart: "Cart", cart_title: "Cart", cart_empty: "Your cart is empty", cart_empty_hint: "Pick an item and tap \"Add to cart\".",
    cart_add: "Add to cart", cart_added: "Added to cart ✅", cart_buy_now: "Pay now",
    cart_total: "Total", cart_pay: "Pay for everything", cart_clear: "Clear cart",
    cart_clear_confirm: "Clear the cart?", cart_to_self: "Myself", cart_to: "For",
    cart_items_suffix: "item(s)", cart_go_shop: "Go to shop",
    cart_pay_hint: "Transfer the total to the card in one payment, then tap \"I've paid\".",
    cart_err_generic: "Could not place the order, please try again.",
    cart_err_no_username: "You don't have a public username. Set one in Telegram settings or choose \"A friend\".",
    cart_active_title: "Cart",
    cart_success_hint: "Open the bot chat and tap \"Confirm\" — payment details will arrive there.",
    flow_step_created: "Placed", flow_step_payment: "Payment", flow_step_doing: "In progress", flow_step_done: "Done",
    flow_awaiting_title: "Waiting for payment", flow_awaiting_sub: "Transfer the amount to the card and upload the receipt here — everything else happens in this window.",
    flow_review_title: "Checking your payment", flow_review_sub: "Usually a couple of minutes. This screen updates by itself.",
    flow_doing_title: "Order in progress", flow_doing_sub: "We're working on it. You'll see the result right here.",
    flow_done_title: "Done!", flow_done_sub: "Your order is complete. Thanks for your purchase 🙌",
    flow_rejected_title: "Order cancelled", flow_rejected_sub: "The payment wasn't confirmed. Contact the operator or order again.",
    flow_pay_exact: "Transfer exactly:",
    flow_commission_note: "If your bank charges a transfer fee, add it ON TOP. Exactly this amount must arrive on the card, otherwise the payment won't be confirmed automatically.", flow_minimize: "Minimize (back to shop)", flow_write_operator: "Contact operator",
    flow_tips: ["Checking the recipient…", "Preparing your order…", "Delivering…", "Almost there…"],
    rentals_title: "My rentals", rentals_empty: "No active rentals.",
    rent_ends_in: "Left", rent_days_short: "d", rent_hours_short: "h",
    rent_extend: "Extend", rent_extend_title: "Extend rental", rent_extend_days: "Extend by how many days?",
    rent_extend_until: "New end date", rent_extend_note: "The gift stays on your profile — no need to send the link again.",
    rent_ending_soon: "Ending soon!",
  },
};

let lang = "uz";
function t(key) { return I18N[lang][key] !== undefined ? I18N[lang][key] : key; }

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach(function(el) {
    const key = el.dataset.i18n;
    const val = t(key);
    if (typeof val === "string") el.textContent = val;
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(function(el) {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  renderRentTerms();
  if (currentTab === "ijara") { renderIjara(); renderMyRentals(); }
  else if (currentTab === "savat") renderCart();
  else renderItems();
}

function setActiveFlagUI() {
  Array.prototype.forEach.call(document.querySelectorAll(".lang-flag"), function(btn) {
    btn.classList.toggle("active", btn.dataset.lang === lang);
  });
}

Array.prototype.forEach.call(document.querySelectorAll(".lang-flag"), function(btn) {
  btn.addEventListener("click", function() {
    lang = btn.dataset.lang;
    setActiveFlagUI();
    applyI18n();
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
  });
});
setActiveFlagUI();

/* ---------------- Форматирование ---------------- */
function fmtUZS(n) { return Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ") + " so'm"; }

/* ---------------- Короткое уведомление (тост) ---------------- */
let _toastTimer = null;
function showToast(text) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = text;
  el.classList.remove("hidden");
  el.style.animation = "sheetUp .25s cubic-bezier(.2,.9,.25,1) both";
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(function() { el.classList.add("hidden"); }, 1800);
}

/* ================= КОРЗИНА =================
 * Хранится в localStorage этого устройства: заказ создаётся на сервере только
 * в момент оплаты, поэтому корзина — чисто клиентское "черновое" состояние.
 * Одна строка корзины = один товар с количеством и своим получателем
 * (можно в одном заказе купить звёзды себе и премиум другу).
 */
const CART_KEY = "oson_cart_v1";
const CART_MAX_LINES = 20;
const CART_MAX_QTY = 10;
let cart = [];

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    cart = Array.isArray(parsed) ? parsed.filter(function(l) { return l && l.kind && l.unitPrice > 0; }) : [];
  } catch (e) { cart = []; }  // localStorage может быть недоступен — просто пустая корзина
}

function saveCart() {
  try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch (e) { /* тихо игнорируем */ }
  updateCartBadge();
}

function cartCount() {
  return cart.reduce(function(sum, l) { return sum + l.qty; }, 0);
}

function cartTotal() {
  return cart.reduce(function(sum, l) { return sum + l.unitPrice * l.qty; }, 0);
}

function updateCartBadge() {
  const badge = document.getElementById("cart-badge");
  if (!badge) return;
  const n = cartCount();
  badge.textContent = n > 99 ? "99+" : String(n);
  badge.classList.toggle("hidden", n === 0);
}

/** Одинаковый товар одному и тому же получателю не плодит строки — растёт количество. */
function cartLineKey(line) {
  return [line.kind, line.itemName, line.giftId || "", line.starsAmount || "", line.recipientType, line.recipient || "", line.note || ""].join("|");
}

function addToCart(line) {
  const key = cartLineKey(line);
  const existing = cart.filter(function(l) { return cartLineKey(l) === key; })[0];
  if (existing) {
    existing.qty = Math.min(existing.qty + line.qty, CART_MAX_QTY);
  } else {
    if (cart.length >= CART_MAX_LINES) return false;
    cart.push(line);
  }
  saveCart();
  return true;
}

function cartChangeQty(index, delta) {
  const line = cart[index];
  if (!line) return;
  const next = line.qty + delta;
  if (next < 1) { cartRemove(index); return; }
  if (next > CART_MAX_QTY) return;
  line.qty = next;
  saveCart();
  renderCart();
  if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
}

function cartRemove(index) {
  cart.splice(index, 1);
  saveCart();
  renderCart();
  if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
}

function clearCart() {
  cart = [];
  saveCart();
  renderCart();
}

/**
 * Кладёт в корзину товар, открытый сейчас в модалке оплаты (со всеми
 * выбранными в ней параметрами: получатель, сообщение, количество подарков).
 */
function addActiveItemToCart() {
  const item = activeItem;
  if (!item) return;
  if (["stars", "stars_custom", "premium", "simple_gift"].indexOf(item.kind) === -1) return;

  const errorEl = document.getElementById("modal-error");
  let friendUsername = document.getElementById("gift-username").value.trim();
  if (recipientType === "friend") {
    if (!friendUsername) { errorEl.textContent = t("err_username"); errorEl.classList.remove("hidden"); return; }
    if (friendUsername.charAt(0) !== "@") friendUsername = "@" + friendUsername;
    saveRecentRecipient(friendUsername);
  }

  const note = document.getElementById("gift-message").value.trim();
  const line = {
    uid: "c" + Date.now() + Math.random().toString(16).slice(2, 6),
    kind: item.kind,
    emoji: item.emoji,
    image: item.image || null,
    qty: 1,
    unitPrice: item.price,
    recipientType: recipientType,
    recipient: recipientType === "friend" ? friendUsername : "",
    note: note,
  };

  if (item.kind === "stars") {
    line.starsAmount = item.raw.amount;
    line.itemName = item.raw.amount + " звёзд";
    line.title = item.raw.amount.toLocaleString("ru-RU").replace(/,/g, " ") + " ⭐️";
  } else if (item.kind === "stars_custom") {
    line.starsAmount = item.raw.qty;
    line.itemName = item.raw.qty + " звёзд";
    line.title = item.raw.qty + " ⭐️";
    line.unitPrice = item.price;
  } else if (item.kind === "premium") {
    line.itemName = "Premium — " + item.raw.label;
    line.title = "💎 " + item.raw.label;
  } else if (item.kind === "simple_gift") {
    line.giftId = item.raw.id;
    line.itemName = "Подарок " + item.emoji + " (" + item.raw.star_count + "⭐)";
    line.title = item.emoji + " " + item.raw.star_count + "⭐";
    line.qty = giftQty;                 // количество, выбранное в модалке
    line.unitPrice = item.raw.price_uzs;  // цена за ОДНУ штуку
  }

  if (!addToCart(line)) { showToast("🛒 " + t("cart_title") + " — max " + CART_MAX_LINES); return; }

  if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  closeModal();
  showToast(t("cart_added"));
}

function cartLineLabel(line) {
  if (line.recipientType === "friend" && line.recipient) return line.recipient;
  return t("cart_to_self");
}

function renderCart() {
  const listEl = document.getElementById("cart-list");
  const checkoutEl = document.getElementById("cart-checkout");
  const clearBtn = document.getElementById("cart-clear-btn");
  if (!listEl) return;

  if (!cart.length) {
    listEl.innerHTML =
      '<div class="glass-card rounded-[22px] p-8 text-center text-gray-400">' +
        '<p class="text-3xl mb-2">🛒</p>' +
        '<p class="text-[14px] font-semibold text-white mb-1">' + t("cart_empty") + '</p>' +
        '<p class="text-[12px] mb-4">' + t("cart_empty_hint") + '</p>' +
        '<button onclick="switchTab(\'asosiy\')" class="press pill-gold rounded-xl px-4 py-2 text-[12px] font-semibold">' + t("cart_go_shop") + '</button>' +
      '</div>';
    checkoutEl.classList.add("hidden");
    clearBtn.classList.add("hidden");
    return;
  }

  listEl.innerHTML = cart.map(function(line, i) {
    const iconHTML = line.image
      ? '<img src="' + line.image + '" class="w-12 h-12 rounded-xl object-cover flex-shrink-0" onerror="this.replaceWith(Object.assign(document.createElement(\'div\'),{className:\'w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center text-xl flex-shrink-0\',textContent:\'' + line.emoji + '\'}))" />'
      : '<div class="w-12 h-12 rounded-xl bg-white/[0.06] flex items-center justify-center text-xl flex-shrink-0">' + line.emoji + '</div>';

    return '<div class="glass-card rounded-[20px] p-3 flex items-center gap-3">' +
      iconHTML +
      '<div class="min-w-0 flex-1">' +
        '<div class="text-[13px] font-semibold text-white truncate">' + line.title + '</div>' +
        '<div class="text-[10px] text-gray-500 truncate">' + t("cart_to") + ': ' + cartLineLabel(line) + '</div>' +
        '<div class="text-[12px] font-bold text-neon-yellow mt-0.5">' + fmtUZS(line.unitPrice * line.qty) + '</div>' +
      '</div>' +
      '<div class="flex flex-col items-end gap-1.5 flex-shrink-0">' +
        '<button onclick="cartRemove(' + i + ')" class="press text-gray-500 text-[15px] leading-none px-1">✕</button>' +
        '<div class="flex items-center gap-2 bg-white/[0.05] rounded-xl px-1.5 py-1">' +
          '<button onclick="cartChangeQty(' + i + ',-1)" class="press w-6 h-6 rounded-lg bg-white/10 text-white text-sm font-bold leading-none">−</button>' +
          '<span class="text-[12px] font-bold w-4 text-center">' + line.qty + '</span>' +
          '<button onclick="cartChangeQty(' + i + ',1)" class="press w-6 h-6 rounded-lg bg-white/10 text-white text-sm font-bold leading-none">+</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }).join("");

  document.getElementById("cart-total").textContent = fmtUZS(cartTotal());
  checkoutEl.classList.remove("hidden");
  clearBtn.classList.remove("hidden");

  getPaymentInfo().then(function(pay) {
    document.getElementById("cart-card-number").textContent = pay.card_number || "—";
    document.getElementById("cart-card-holder").textContent = pay.card_holder || "—";
  }).catch(function() { /* реквизиты просто останутся прочерком */ });
}

/** Отправка всей корзины одним заказом — одна сумма, один чек. */
let cartOrderInFlight = false;
async function submitCartOrder() {
  if (cartOrderInFlight || !cart.length) return;
  const errorEl = document.getElementById("cart-error");
  const btn = document.getElementById("cart-pay-btn");
  errorEl.classList.add("hidden");

  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) {
    errorEl.textContent = t("history_open_bot");
    errorEl.classList.remove("hidden");
    return;
  }

  const items = cart.map(function(line) {
    return {
      category: line.kind,
      item_name: line.itemName,
      price: line.unitPrice,
      quantity: line.qty,
      stars_amount: line.starsAmount,
      gift_id: line.giftId,
      recipient: line.recipient,
      recipient_type: line.recipientType,
      note: line.note || undefined,
    };
  });

  cartOrderInFlight = true;
  const prev = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="inline-block w-4 h-4 border-2 border-white/40 border-t-white rounded-full align-middle" style="animation: spin .7s linear infinite;"></span>';

  try {
    const res = await fetch(base + "/public/place_cart_order", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData, items: items }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      errorEl.textContent = data.error === "no_username" ? t("cart_err_no_username") : t("cart_err_generic");
      errorEl.classList.remove("hidden");
      return;
    }
    // Корзина оформлена одним заказом — очищаем её и переходим на экран
    // живого статуса, дальше всё происходит там же, внутри витрины.
    const total = cartTotal();
    const count = cartCount();
    clearCart();
    openOrderFlow({ cart_id: data.cart_id, order_id: data.order_id }, {
      order_id: data.order_id,
      cart_id: data.cart_id,
      item_name: "🛒 " + count + " " + t("cart_items_suffix"),
      recipient: "",
      price_uzs: total,
      pay_amount: data.pay_amount,
      card_number: data.card_number,
      card_holder: data.card_holder,
    });
  } catch (e) {
    errorEl.textContent = t("ao_err_network");
    errorEl.classList.remove("hidden");
  } finally {
    cartOrderInFlight = false;
    btn.disabled = false;
    btn.innerHTML = prev;
  }
}

/**
 * Подтверждение действия. В Telegram лучше спрашивать его нативным
 * showConfirm — обычный window.confirm в WebView клиента может быть
 * заблокирован, и тогда кнопка молча ничего не делала бы.
 */
function askConfirm(text, onYes) {
  if (tg && tg.showConfirm) { tg.showConfirm(text, function(ok) { if (ok) onYes(); }); return; }
  if (confirm(text)) onYes();
}

loadCart();
updateCartBadge();

document.getElementById("cart-clear-btn").addEventListener("click", function() {
  if (!cart.length) return;
  askConfirm(t("cart_clear_confirm"), clearCart);
});

/* ---------------- Загрузка каталога ---------------- */
const catalog = { stars: [], premium: [], simple_gift: [], nft_rent: [] };
let currentCategory = "stars";
let currentTab = "asosiy";
let currentRentSort = "recently_touch";
let currentRentCollection = null;
let currentRentCollectionName = null;

async function loadCatalog(cat, forceReload) {
  if (catalog[cat].length && !forceReload) return catalog[cat];
  const res = await fetch("/api/" + cat);
  if (!res.ok) throw new Error("bad response " + cat);
  const data = await res.json();
  catalog[cat] = data.map(normalizeItem(cat));
  return catalog[cat];
}

async function fetchRentPage(cursor) {
  let url = "/api/nft_rent?sort_by=" + currentRentSort;
  if (currentRentCollection) url += "&collection_address=" + encodeURIComponent(currentRentCollection);
  if (cursor) url += "&cursor=" + encodeURIComponent(cursor);
  const res = await fetch(url);
  if (!res.ok) throw new Error("bad response nft_rent");
  const data = await res.json();
  const mapped = data.items.map(normalizeItem("nft_rent"));
  return { items: mapped, nextCursor: data.next_cursor };
}

function normalizeItem(cat) {
  return function(raw) {
    if (cat === "stars") return { kind: "stars", title: raw.amount.toLocaleString("ru-RU") + " Stars", price: raw.price_uzs, emoji: "⭐️", raw: raw };
    if (cat === "premium") return { kind: "premium", title: raw.label, price: raw.price_uzs, emoji: "👑", raw: raw };
    if (cat === "simple_gift") return { kind: "simple_gift", title: raw.star_count + "⭐", price: raw.price_uzs, emoji: raw.sticker_emoji || "🎁", image: raw.image_url || null, raw: raw };
    if (cat === "nft_rent") return { kind: "nft_rent", title: raw.name, price: raw.price_per_day_uzs_with_markup, emoji: pickGiftEmoji(raw.name), image: raw.image_url, previewUrl: raw.preview_url, raw: raw };
  };
}

// Фото у API нет, подбираем эмодзи по названию для узнаваемости карточки
function pickGiftEmoji(name) {
  const n = (name || "").toLowerCase();
  if (n.includes("pepe")) return "🐸";
  if (n.includes("cat")) return "🐱";
  if (n.includes("bird")) return "🐦";
  if (n.includes("wine")) return "🍷";
  if (n.includes("hat") || n.includes("cap")) return "🎩";
  if (n.includes("watch")) return "⌚️";
  if (n.includes("ring")) return "💍";
  if (n.includes("bear")) return "🧸";
  if (n.includes("rose") || n.includes("flower")) return "🌹";
  if (n.includes("crown")) return "👑";
  return "🖼";
}

async function renderItems() {
  const grid = document.getElementById("products-grid");
  // Stars — компактные карточки с цифрой, помещается 3 в ряд.
  // Gift — картинка главный герой, ей нужно место: 2 в ряд.
  grid.className = currentCategory === "stars"
    ? "p-4 grid grid-cols-3 gap-3 max-w-sm mx-auto"
    : "p-4 grid grid-cols-2 gap-3 max-w-sm mx-auto";

  if (currentCategory === "premium") { await renderPremiumList(); return; }
  document.getElementById("premium-list").classList.add("hidden");
  grid.classList.remove("hidden");

  grid.innerHTML = skeletonHTML(6, currentCategory === "stars" ? "h-[104px]" : "h-[168px]");
  let items;
  try { items = await loadCatalog(currentCategory); }
  catch (e) { grid.innerHTML = '<p class="col-span-full text-center text-xs text-gray-500 py-8">' + t("empty") + '</p>'; return; }

  if (!items.length) { grid.innerHTML = '<p class="col-span-full text-center text-xs text-gray-500 py-8">' + t("empty") + '</p>'; return; }

  const customCardHTML = currentCategory === "stars"
    ? '<div id="stars-custom-card" class="glass-card press rounded-[20px] p-3 flex flex-col items-center justify-center text-center cursor-pointer min-h-[104px]" style="border-style: dashed;">' +
        '<div class="text-2xl">✏️</div>' +
        '<div class="text-[10px] text-gray-300 mt-1.5 leading-tight">' + t("custom_amount") + '</div>' +
        '<div class="text-[9px] text-gray-500 mt-0.5">' + t("custom_amount_hint") + '</div>' +
      '</div>'
    : "";

  grid.innerHTML = items.map(function(it, i) {
    const isPopularStars = currentCategory === "stars" && it.raw && it.raw.amount === 1000;
    const popularBadge = isPopularStars
      ? '<span class="badge-popular absolute -top-1.5 right-1.5 pill-gold text-[8px] font-bold px-2 py-0.5 rounded-full leading-none z-10">' + t("badge_popular") + '</span>'
      : "";
    const cardBase = '<div data-i="' + i + '" class="product-card glass-card press rounded-[20px] cursor-pointer relative overflow-visible' + (isPopularStars ? " card-popular" : "") + '">';

    // STARS: героем делаем само число, а не одинаковую жёлтую звезду —
    // раньше 15 карточек выглядели идентично, различал только мелкий текст.
    // Плюс показываем цену за 1 звезду: чем больше пакет, тем она ниже,
    // так человек видит выгоду и берёт пакет побольше.
    if (currentCategory === "stars") {
      const amount = it.raw.amount;
      const perStar = Math.round(it.price / amount);
      return cardBase +
        popularBadge +
        '<div class="p-3 flex flex-col items-center text-center">' +
          '<div class="flex items-baseline gap-0.5 mt-1">' +
            '<span class="text-[22px] font-black text-white leading-none tracking-tight">' + amount.toLocaleString("ru-RU").replace(/,/g, " ") + '</span>' +
            '<span class="text-[11px]">⭐️</span>' +
          '</div>' +
          '<div class="text-[11px] font-bold text-neon-yellow mt-2">' + fmtUZS(it.price) + '</div>' +
          '<div class="text-[9px] text-gray-500 mt-0.5">' + perStar + " " + t("per_star") + '</div>' +
        '</div>' +
      '</div>';
    }

    // GIFT: картинка — главный герой, ей отдаём всю ширину карточки.
    const iconHTML = it.image
      ? '<img src="' + it.image + '" loading="lazy" class="w-full h-full object-cover animated-gift" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';" />' +
        '<div class="absolute inset-0 hidden items-center justify-center text-4xl animated-gift">' + it.emoji + '</div>'
      : '<div class="absolute inset-0 flex items-center justify-center text-4xl animated-gift">' + it.emoji + '</div>';
    return cardBase +
      popularBadge +
      '<div class="relative w-full aspect-square rounded-t-[20px] overflow-hidden" style="background: radial-gradient(circle at 50% 35%, rgba(255,255,255,0.07), transparent 70%);">' + iconHTML + '</div>' +
      '<div class="px-2 py-2.5 text-center">' +
        '<div class="text-[10px] text-gray-400 leading-tight">' + it.title + '</div>' +
        '<div class="text-[11px] font-bold text-neon-yellow mt-1">' + fmtUZS(it.price) + '</div>' +
      '</div>' +
    '</div>';
  }).join("") + customCardHTML;

  const customCard = document.getElementById("stars-custom-card");
  if (customCard) customCard.addEventListener("click", openCustomStarsModal);

  Array.prototype.forEach.call(grid.querySelectorAll(".product-card"), function(card) {
    card.addEventListener("click", function() { openModal(items[Number(card.dataset.i)]); });
  });
}

/* ---------------- Ijara (аренда) — с догрузкой страниц ---------------- */
let rentNextCursor = null;
let rentLoadingMore = false;

// Карточка аренды в стиле MarketApp: картинка с бейджем срока, название,
// цена + "so'm" + "· N kun", кнопка "Ijaraga olish". Кликается ВСЯ карточка,
// не только кнопка.
function rentCardHTML(it, i) {
  const imgBlock = it.image
    ? '<img src="' + it.image + '" loading="lazy" class="absolute inset-0 w-full h-full object-cover" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';" />' +
      '<div class="absolute inset-0 hidden items-center justify-center"><span class="text-6xl animated-gift">' + it.emoji + '</span></div>'
    : '<div class="absolute inset-0 flex items-center justify-center"><span class="text-6xl animated-gift">' + it.emoji + '</span></div>';

  const discountBadge = it.raw.discount_per_day > 0
    ? '<span class="absolute top-2 right-2 bg-red-500/80 backdrop-blur text-[10px] font-bold px-2 py-1 rounded-lg text-white">-' + it.raw.discount_per_day + '%</span>'
    : '';

  const numberBadge = it.raw.number
    ? '<span class="text-[11px] text-gray-500 font-mono">#' + it.raw.number + '</span>'
    : '';

  return '<div data-i="' + i + '" class="rent-card glass-card press rounded-[22px] overflow-hidden flex flex-col cursor-pointer">' +
    '<div class="rent-img relative h-44">' +
      imgBlock +
      discountBadge +
      '<span class="absolute bottom-2 right-2 bg-black/50 backdrop-blur-md text-[10px] font-semibold px-2 py-1 rounded-lg text-gray-200 border border-white/10">' +
        t("rent_from") + ' ' + it.raw.min_duration_days + '-' + it.raw.max_duration_days + ' ' + t("rent_days_suffix") +
      '</span>' +
    '</div>' +
    '<div class="p-3.5 flex flex-col gap-1.5">' +
      '<div class="flex items-center justify-between">' +
        '<div class="text-sm font-bold text-white truncate">' + it.title + '</div>' +
        numberBadge +
      '</div>' +
      '<div class="text-sm font-bold text-neon-yellow">' + fmtUZS(it.price) + ' <span class="text-[11px] text-gray-400 font-normal">· 1 ' + t("rent_days_suffix") + '</span></div>' +
      '<button data-i="' + i + '" class="rent-btn press mt-2 w-full py-3 rounded-2xl btn-primary font-semibold text-white text-sm">' + t("rent_btn") + '</button>' +
    '</div>' +
  '</div>';
}

function renderRentGrid() {
  const grid = document.getElementById("ijara-grid");
  const items = catalog.nft_rent;

  grid.innerHTML = items.map(function(it, i) { return rentCardHTML(it, i); }).join("");

  Array.prototype.forEach.call(grid.querySelectorAll(".rent-card"), function(card) {
    card.addEventListener("click", function(e) {
      if (e.target.closest(".rent-btn")) return; // кнопка сама откроет — избегаем двойного триггера
      openModal(items[Number(card.dataset.i)]);
    });
  });
  Array.prototype.forEach.call(grid.querySelectorAll(".rent-btn"), function(btn) {
    btn.addEventListener("click", function() { openModal(items[Number(btn.dataset.i)]); });
  });

  renderLoadMoreButton();
}

function renderLoadMoreButton() {
  const existing = document.getElementById("rent-load-more");
  if (existing) existing.remove();

  if (!rentNextCursor) return;

  const btn = document.createElement("button");
  btn.id = "rent-load-more";
  btn.className = "col-span-2 mt-1 py-3.5 rounded-2xl pill press text-sm font-semibold";
  btn.textContent = t("load_more");
  btn.addEventListener("click", loadMoreRent);
  document.getElementById("ijara-grid").appendChild(btn);
}

async function loadMoreRent() {
  if (rentLoadingMore) return;
  rentLoadingMore = true;
  const btn = document.getElementById("rent-load-more");
  if (btn) { btn.textContent = "..."; btn.disabled = true; }

  try {
    const page = await fetchRentPage(rentNextCursor);
    catalog.nft_rent = catalog.nft_rent.concat(page.items);
    rentNextCursor = page.nextCursor;
    renderRentGrid();
  } catch (e) { /* тихо игнорируем — кнопка просто останется */ }

  rentLoadingMore = false;
}

async function renderIjara(reset) {
  const grid = document.getElementById("ijara-grid");

  if (reset || !catalog.nft_rent.length) {
    grid.innerHTML = skeletonHTML(4, "h-80");
    catalog.nft_rent = [];
    rentNextCursor = null;

    try {
      const page = await fetchRentPage(null);
      catalog.nft_rent = page.items;
      rentNextCursor = page.nextCursor;
    } catch (e) {
      grid.innerHTML = '<p class="col-span-2 text-center text-xs text-gray-500 py-8">' + t("empty") + '</p>';
      return;
    }
  }

  if (!catalog.nft_rent.length) { grid.innerHTML = '<p class="col-span-2 text-center text-xs text-gray-500 py-8">' + t("empty") + '</p>'; return; }
  renderRentGrid();
}

document.getElementById("rent-sort-select").addEventListener("change", function(e) {
  currentRentSort = e.target.value;
  renderIjara(true);
});

/* ---------------- Фильтр по коллекции ---------------- */
let _collectionsCache = null;

document.getElementById("rent-collection-btn").addEventListener("click", openCollectionModal);
document.getElementById("collection-close-btn").addEventListener("click", closeCollectionModal);
document.getElementById("collection-modal").addEventListener("click", function(e) {
  if (e.target === document.getElementById("collection-modal")) closeCollectionModal();
});

async function openCollectionModal() {
  const modal = document.getElementById("collection-modal");
  const content = document.getElementById("collection-content");
  const listEl = document.getElementById("collection-list");

  modal.classList.remove("hidden");
  requestAnimationFrame(function() {
    modal.classList.remove("opacity-0");
    content.classList.remove("translate-y-full");
  });

  if (!_collectionsCache) {
    listEl.innerHTML = skeletonHTML(4, "h-12");
    try {
      const res = await fetch("/api/rent_collections");
      _collectionsCache = await res.json();
    } catch (e) { _collectionsCache = []; }
  }

  paintCollectionList();
}

function paintCollectionList() {
  const listEl = document.getElementById("collection-list");
  const rows = [{ name: t("collection_all"), address: null, image: null }].concat(_collectionsCache || []);

  listEl.innerHTML = rows.map(function(c) {
    const selected = c.address === currentRentCollection;
    const iconHTML = c.image
      ? '<img src="' + c.image + '" alt="" class="w-8 h-8 rounded-lg object-cover flex-shrink-0" onerror="this.replaceWith(Object.assign(document.createElement(\'div\'),{className:\'w-8 h-8 rounded-lg bg-white/10 flex-shrink-0\'}))">'
      : '<div class="w-8 h-8 rounded-lg bg-white/10 flex-shrink-0"></div>';
    return '<div data-address="' + (c.address || "") + '" data-name="' + c.name + '" class="collection-row press flex items-center gap-3 rounded-2xl p-3 cursor-pointer border ' +
      (selected ? "bg-neon-blue/10 border-neon-blue/50" : "bg-white/[0.04] border-white/[0.08]") + '">' +
      iconHTML +
      '<span class="text-sm font-medium text-white flex-1">' + c.name + '</span>' +
      (selected ? '<span class="text-neon-blue text-sm">✓</span>' : '') +
    '</div>';
  }).join("");

  Array.prototype.forEach.call(listEl.querySelectorAll(".collection-row"), function(row) {
    row.addEventListener("click", function() {
      currentRentCollection = row.dataset.address || null;
      currentRentCollectionName = currentRentCollection ? row.dataset.name : null;
      document.getElementById("rent-collection-label").textContent = currentRentCollectionName || t("collection_all");
      closeCollectionModal();
      renderIjara(true);
    });
  });
}

function closeCollectionModal() {
  const modal = document.getElementById("collection-modal");
  const content = document.getElementById("collection-content");
  content.classList.add("translate-y-full");
  modal.classList.add("opacity-0");
  setTimeout(function() { modal.classList.add("hidden"); }, 300);
}

/* ---------------- Premium: список с радио-выбором ---------------- */
let selectedPremiumIndex = 0;

async function renderPremiumList() {
  document.getElementById("products-grid").classList.add("hidden");
  const container = document.getElementById("premium-list");
  container.classList.remove("hidden");

  const optionsEl = document.getElementById("premium-options");
  optionsEl.innerHTML = skeletonHTML(3, "h-16");

  let items;
  try { items = await loadCatalog("premium"); }
  catch (e) { optionsEl.innerHTML = '<p class="text-center text-xs text-gray-500 py-8">' + t("empty") + '</p>'; return; }

  if (!items.length) { optionsEl.innerHTML = '<p class="text-center text-xs text-gray-500 py-8">' + t("empty") + '</p>'; return; }
  if (selectedPremiumIndex >= items.length) selectedPremiumIndex = 0;

  function paint() {
    // "Популярный" — на тариф с самым долгим сроком (обычно 12 месяцев).
    // Если совпадений несколько (напр. "12 месяцев" и "12 месяцев как подарок"),
    // помечаем только первый по списку, чтобы бейдж не задублировался.
    const durationOf = function(title) {
      const m = /^(\d+)/.exec(title || "");
      return m ? parseInt(m[1], 10) : 0;
    };
    const maxDuration = Math.max.apply(null, items.map(function(it) { return durationOf(it.title); }));
    let popularMarked = false;

    optionsEl.innerHTML = items.map(function(it, i) {
      const selected = i === selectedPremiumIndex;
      const isPopular = !popularMarked && maxDuration > 0 && durationOf(it.title) === maxDuration;
      if (isPopular) popularMarked = true;
      const popularBadge = isPopular
        ? '<span class="badge-popular absolute -top-2 right-3 pill-gold text-[9px] font-bold px-2 py-0.5 rounded-full leading-none">' + t("badge_popular") + '</span>'
        : "";
      return '<div data-i="' + i + '" class="premium-option press flex items-center justify-between gap-3 rounded-2xl p-4 cursor-pointer border relative ' +
        (selected ? "bg-neon-blue/10 border-neon-blue/50" : (isPopular ? "bg-white/[0.04] card-popular" : "bg-white/[0.04] border-white/[0.08]")) + '">' +
        popularBadge +
        '<div class="flex items-center gap-3 min-w-0">' +
          '<span class="w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ' + (selected ? "border-neon-blue" : "border-gray-600") + '">' +
            (selected ? '<span class="w-2.5 h-2.5 rounded-full bg-neon-blue"></span>' : "") +
          '</span>' +
          '<span class="text-[13.5px] font-semibold text-white leading-tight">' + it.title + '</span>' +
        '</div>' +
        '<span class="text-[13.5px] font-bold text-neon-yellow flex-shrink-0">' + fmtUZS(it.price) + '</span>' +
      '</div>';
    }).join("");

    Array.prototype.forEach.call(optionsEl.querySelectorAll(".premium-option"), function(row) {
      row.addEventListener("click", function() {
        selectedPremiumIndex = Number(row.dataset.i);
        paint();
        updatePremiumCta();
      });
    });
  }

  function updatePremiumCta() {
    const btn = document.getElementById("premium-cta-btn");
    const it = items[selectedPremiumIndex];
    btn.textContent = it.title + " " + t("premium_get_suffix");
    btn.onclick = function() { openModal(it); };
  }

  paint();
  updatePremiumCta();
}

function skeletonHTML(n, heightClass) {
  let out = "";
  for (let i = 0; i < n; i++) out += '<div class="skeleton rounded-2xl ' + heightClass + '"></div>';
  return out;
}

function setCategory(cat) {
  currentCategory = cat;
  Array.prototype.forEach.call(document.querySelectorAll(".cat-btn"), function(btn) {
    btn.className = "cat-btn press px-4 py-2 rounded-full pill text-xs whitespace-nowrap";
  });
  document.getElementById("cat-" + cat).className = "cat-btn press px-4 py-2 rounded-full pill-gold text-xs font-semibold whitespace-nowrap";
  renderItems();
}

function switchTab(tab) {
  currentTab = tab;
  ["asosiy","ijara","savat","tarix","top","profil"].forEach(function(x) {
    document.getElementById("view-" + x).classList.add("view-hidden");
  });
  document.getElementById("view-" + tab).classList.remove("view-hidden");
  Array.prototype.forEach.call(document.querySelectorAll(".nav-btn"), function(btn) {
    btn.classList.remove("text-neon-blue"); btn.classList.add("text-gray-500");
  });
  document.getElementById("tab-" + tab).classList.remove("text-gray-500");
  document.getElementById("tab-" + tab).classList.add("text-neon-blue");
  if (tab === "ijara") { renderIjara(); renderMyRentals(); }
  if (tab === "savat") renderCart();
  if (tab === "tarix") renderHistory();
  if (tab === "top") renderLeaderboard(currentTopPeriod);
  if (tab === "profil") { initProfile(); renderProfileStats(); }
}

/* ---------------- Модалка оплаты ---------------- */
let activeItem = null;
let recipientType = "self";
let rentDays = 1;

const modal = document.getElementById("payment-modal");
const modalContent = document.getElementById("payment-content");

function setRecipient(type) {
  recipientType = type;
  const btnSelf = document.getElementById("rec-self");
  const btnFriend = document.getElementById("rec-friend");
  const userField = document.getElementById("username-field");
  const activeCls = "flex-1 py-1.5 rounded-lg bg-white/10 font-semibold text-xs text-white shadow-inner";
  const inactiveCls = "flex-1 py-1.5 rounded-lg text-gray-400 font-semibold text-xs";

  if (type === "self") {
    btnSelf.className = activeCls; btnFriend.className = inactiveCls;
    userField.classList.add("hidden");
  } else {
    btnFriend.className = activeCls; btnSelf.className = inactiveCls;
    userField.classList.remove("hidden");
    showRecentRecipientChip();
  }
  document.getElementById("modal-error").classList.add("hidden");
}

function showRecentRecipientChip() {
  let recent = null;
  try { recent = localStorage.getItem("oson_last_recipient"); } catch (e) { /* недоступно — просто не покажем чип */ }

  const chip = document.getElementById("recent-recipient-chip");
  const btn = document.getElementById("recent-recipient-btn");
  if (!recent) { chip.classList.add("hidden"); return; }

  btn.textContent = recent;
  btn.onclick = function() { document.getElementById("gift-username").value = recent; };
  chip.classList.remove("hidden");
}

function saveRecentRecipient(username) {
  try { localStorage.setItem("oson_last_recipient", username); } catch (e) { /* тихо игнорируем */ }
}

function stepDays(delta) {
  if (!activeItem) return;
  let min, max;
  if (activeItem.kind === "nft_rent") {
    min = activeItem.raw.min_duration_days; max = activeItem.raw.max_duration_days;
  } else if (activeItem.kind === "nft_rent_extend") {
    min = activeItem.raw.min_days; max = activeItem.raw.max_days;
  } else {
    return;
  }
  const next = rentDays + delta;
  if (next < min || next > max) return;
  rentDays = next;
  document.getElementById("days-value").textContent = rentDays;
  document.getElementById("modal-price").textContent = fmtUZS(activeItem.price * rentDays);
  if (activeItem.kind === "nft_rent_extend") updateExtendUntilLabel();
}

/** Показывает, до какой даты сдвинется аренда при выбранном числе дней. */
function updateExtendUntilLabel() {
  const el = document.getElementById("extend-note");
  if (!el || !activeItem || activeItem.kind !== "nft_rent_extend") return;
  const ends = new Date(String(activeItem.raw.ends_at).replace(" ", "T") + "Z");
  const newEnds = new Date(ends.getTime() + rentDays * 86400000);
  el.innerHTML = t("rent_extend_note") +
    '<br><span class="text-white font-semibold">' + t("rent_extend_until") + ": " +
    newEnds.toISOString().slice(0, 10) + '</span>';
}

const GIFT_QTY_MAX = 10;
let giftQty = 1;
function stepGiftQty(delta) {
  if (!activeItem || activeItem.kind !== "simple_gift") return;
  const next = giftQty + delta;
  if (next < 1 || next > GIFT_QTY_MAX) return;
  giftQty = next;
  document.getElementById("gift-qty-value").textContent = giftQty;
  document.getElementById("modal-price").textContent = fmtUZS(activeItem.price * giftQty);
}

let _starsRateCache = null;
async function openCustomStarsModal() {
  if (!_starsRateCache) {
    const res = await fetch("/api/stars_rate");
    _starsRateCache = await res.json();
  }
  const rate = _starsRateCache.rate_uzs_per_star;
  const qty = 50;
  openModal({
    kind: "stars_custom",
    title: t("custom_amount"),
    price: rate * qty,
    emoji: "✏️",
    raw: { rate: rate, qty: qty, min: _starsRateCache.min_stars || 50 },
  });
}

async function openModal(item) {
  activeItem = item;
  if (item.kind === "nft_rent") rentDays = item.raw.min_duration_days;
  else if (item.kind === "nft_rent_extend") rentDays = item.raw.min_days || 1;
  else rentDays = 1;

  document.getElementById("modal-title").textContent = item.title + (item.raw && item.raw.number ? " #" + item.raw.number : "");
  const emojiEl = document.getElementById("modal-emoji");
  if (item.image) {
    const bigClass = item.kind === "nft_rent" ? "w-24 h-24" : "w-10 h-10";
    emojiEl.className = "rounded-2xl overflow-hidden flex-shrink-0 animated-gift";
    emojiEl.innerHTML = '<img src="' + item.image + '" class="' + bigClass + ' rounded-2xl object-cover" onerror="this.parentElement.textContent=\'' + item.emoji + '\';" />';
  } else {
    emojiEl.className = "text-4xl animated-gift";
    emojiEl.textContent = item.emoji;
  }
  const isRentLike = item.kind === "nft_rent" || item.kind === "nft_rent_extend";
  document.getElementById("modal-price").textContent = fmtUZS(isRentLike ? item.price * rentDays : item.price);
  document.getElementById("gift-message").value = "";
  document.getElementById("gift-username").value = "";
  document.getElementById("modal-error").classList.add("hidden");
  setRecipient("self");

  // Продление: получателя выбирать не нужно — подарок уже у клиента в профиле
  const isExtend = item.kind === "nft_rent_extend";
  document.getElementById("recipient-field").classList.toggle("hidden", isExtend);
  if (isExtend) document.getElementById("username-field").classList.add("hidden");
  const extendNote = document.getElementById("extend-note");
  extendNote.classList.toggle("hidden", !isExtend);
  if (isExtend) updateExtendUntilLabel();

  // "В корзину" — только для обычных товаров: у аренды свой срок и комиссия сети
  const addCartBtn = document.getElementById("add-to-cart-btn");
  const cartable = ["stars", "stars_custom", "premium", "simple_gift"].indexOf(item.kind) !== -1;
  addCartBtn.classList.toggle("hidden", !cartable);

  document.getElementById("rent-days-field").classList.toggle("hidden", !isRentLike);
  if (isRentLike) document.getElementById("days-value").textContent = rentDays;

  document.getElementById("gift-quantity-field").classList.toggle("hidden", item.kind !== "simple_gift");
  if (item.kind === "simple_gift") {
    giftQty = 1;
    document.getElementById("gift-qty-value").textContent = giftQty;
    document.getElementById("modal-price").textContent = fmtUZS(item.price * giftQty);
  }

  const starsCustomField = document.getElementById("stars-custom-field");
  const starsCustomInput = document.getElementById("stars-custom-input");
  starsCustomField.classList.toggle("hidden", item.kind !== "stars_custom");
  if (item.kind === "stars_custom") {
    starsCustomInput.value = item.raw.qty || 50;
    starsCustomInput.oninput = function() {
      let qty = parseInt(starsCustomInput.value, 10);
      if (isNaN(qty) || qty < 50) qty = 50;
      item.raw.qty = qty;
      item.price = qty * item.raw.rate;
      document.getElementById("modal-price").textContent = fmtUZS(item.price);
    };
  }

  const previewBtn = document.getElementById("preview-gift-btn");
  if (item.kind === "nft_rent" && item.previewUrl) {
    previewBtn.classList.remove("hidden");
    previewBtn.onclick = function() {
      if (tg && tg.openTelegramLink) tg.openTelegramLink(item.previewUrl);
      else window.open(item.previewUrl, "_blank");
    };
  } else {
    previewBtn.classList.add("hidden");
    previewBtn.onclick = null;
  }

  try {
    const pay = await getPaymentInfo();
    document.getElementById("pay-card-number").textContent = pay.card_number || "—";
    document.getElementById("pay-card-holder").textContent = pay.card_holder || "—";
  } catch (e) {
    document.getElementById("pay-card-number").textContent = "—";
  }

  if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
  modal.classList.remove("hidden");
  requestAnimationFrame(function() {
    modal.classList.remove("opacity-0");
    modalContent.classList.remove("translate-y-full");
  });
}

function closeModal() {
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); // убрать клавиатуру
  modalContent.classList.add("translate-y-full");
  modal.classList.add("opacity-0");
  setTimeout(function() { modal.classList.add("hidden"); }, 300);
}

// Клик по затемнённому фону вокруг шторки — тоже закрывает
modal.addEventListener("click", function(e) {
  if (e.target === modal) closeModal();
});

/* ---------------- Свайп вниз для закрытия шторки ---------------- */
(function enableSwipeToDismiss() {
  const handle = document.getElementById("sheet-handle");
  let startY = 0, currentY = 0, dragging = false;

  function onStart(y) {
    dragging = true;
    startY = y;
    currentY = y;
    modalContent.style.transition = "none";
  }
  function onMove(y) {
    if (!dragging) return;
    currentY = y;
    const delta = Math.max(0, currentY - startY);
    modalContent.style.transform = "translateY(" + delta + "px)";
  }
  function onEnd() {
    if (!dragging) return;
    dragging = false;
    modalContent.style.transition = "";
    const delta = currentY - startY;
    modalContent.style.transform = "";
    if (delta > 90) {
      closeModal();
    }
  }

  handle.addEventListener("touchstart", function(e) { onStart(e.touches[0].clientY); }, { passive: true });
  handle.addEventListener("touchmove", function(e) { onMove(e.touches[0].clientY); }, { passive: true });
  handle.addEventListener("touchend", onEnd);

  // На всякий случай (десктоп/тестирование) — те же события мышью
  handle.addEventListener("mousedown", function(e) { onStart(e.clientY); });
  document.addEventListener("mousemove", function(e) { if (dragging) onMove(e.clientY); });
  document.addEventListener("mouseup", onEnd);
})();

let _paymentInfoCache = null;
async function getPaymentInfo() {
  if (_paymentInfoCache) return _paymentInfoCache;
  const res = await fetch("/api/payment_info");
  _paymentInfoCache = await res.json();
  return _paymentInfoCache;
}

function copyCard() {
  getPaymentInfo().then(function(p) {
    navigator.clipboard.writeText((p.card_number || "").replace(/\s/g, ""));
    if (tg && tg.showAlert) tg.showAlert(t("copied")); else alert(t("copied"));
  });
}

function openTgUsername(username) {
  if (!username) return;
  if (tg && tg.openTelegramLink) tg.openTelegramLink("https://t.me/" + username);
  else window.open("https://t.me/" + username, "_blank");
}

async function initSupportInfo() {
  try {
    const res = await fetch("/api/support_info");
    const info = await res.json();

    if (info.operator_username) {
      document.getElementById("operator-handle").textContent = "@" + info.operator_username;
      document.getElementById("row-operator").onclick = function() { openTgUsername(info.operator_username); };
    }
    if (info.channel_username) {
      const row = document.getElementById("row-channel");
      row.classList.remove("hidden"); row.classList.add("flex");
      document.getElementById("channel-handle").textContent = "@" + info.channel_username;
      row.onclick = function() { openTgUsername(info.channel_username); };
    }
    if (info.orders_channel_username) {
      const row = document.getElementById("row-orders");
      row.classList.remove("hidden"); row.classList.add("flex");
      document.getElementById("orders-handle").textContent = "@" + info.orders_channel_username;
      row.onclick = function() { openTgUsername(info.orders_channel_username); };
    }
  } catch (e) { /* тихо игнорируем — строки просто останутся скрытыми/пустыми */ }
}

/* ---------------- Отправка заказа боту ---------------- */
// Защита от двойного заказа: пока предыдущий запрос ещё летит на сервер,
// повторные нажатия "To'ladim" игнорируются. Без этого двойной тап (частая
// вещь на телефоне, особенно при медленном интернете) создавал ДВА заказа.
let orderInFlight = false;

function sendPaymentInfo() {
  if (orderInFlight) return;
  const errorEl = document.getElementById("modal-error");
  let friendUsername = document.getElementById("gift-username").value.trim();

  if (recipientType === "friend") {
    if (!friendUsername) { errorEl.textContent = t("err_username"); errorEl.classList.remove("hidden"); return; }
    if (friendUsername.charAt(0) !== "@") friendUsername = "@" + friendUsername;
  }

  // Юзернейм для "себе" достаём на СЕРВЕРЕ (бот всегда точно знает,
  // кто написал) — клиентский tg.initDataUnsafe не всегда надёжен
  // (кэш вебвью и т.п.), поэтому здесь ничего не проверяем и не блокируем.
  const item = activeItem;
  const message = document.getElementById("gift-message").value.trim();
  const recipient = recipientType === "self" ? "" : friendUsername;

  const payload = {
    category: item.kind,
    recipient: recipient,
    recipient_type: recipientType,
    note: message || undefined,
  };

  if (item.kind === "stars") {
    payload.item_name = item.raw.amount + " звёзд"; payload.price = item.raw.price_uzs; payload.quantity = item.raw.amount;
  } else if (item.kind === "stars_custom") {
    payload.item_name = item.raw.qty + " звёзд"; payload.price = item.price; payload.quantity = item.raw.qty;
  } else if (item.kind === "premium") {
    payload.item_name = "Premium — " + item.raw.label; payload.price = item.raw.price_uzs; payload.quantity = 1;
  } else if (item.kind === "simple_gift") {
    payload.item_name = "Подарок " + item.emoji + " (" + item.raw.star_count + "⭐) x" + giftQty;
    payload.price = item.raw.price_uzs * giftQty;
    payload.quantity = giftQty;
    payload.gift_id = item.raw.id;
  } else if (item.kind === "nft_rent") {
    // БАГ БЫЛ ЗДЕСЬ: цену для аренды не клали в payload вообще, и экран после
    // оформления показывал "0 so'm". Точную сумму (с комиссией сети) всё равно
    // считает сервер, но и здесь она теперь не нулевая.
    payload.price = item.price * rentDays;
    payload.item_name = item.raw.name; payload.nft_address = item.raw.nft_address;
    payload.base_price_per_day_gram = item.raw.base_price_per_day_gram;
    payload.min_days = item.raw.min_duration_days; payload.max_days = item.raw.max_duration_days;
    payload.days = rentDays;
  } else if (item.kind === "nft_rent_extend") {
    // Продление: серверу достаточно адреса гифта и числа дней — цену и права
    // на эту аренду он берёт из собственной базы, данным клиента тут не верим.
    payload.price = item.price * rentDays;
    payload.item_name = item.raw.item_name;
    payload.nft_address = item.raw.nft_address;
    payload.days = rentDays;
  }

  if (recipientType === "friend" && friendUsername) saveRecentRecipient(friendUsername);

  // БЫЛО: tg.sendData(...) — работает ТОЛЬКО если мини-апп открыт через
  // растянутую кнопку клавиатуры ("Do'konni ochish"). Через компактную Menu
  // Button ("Открыть" у поля ввода) sendData() вообще не доходит до бота —
  // это ограничение самого Telegram, не баг. Поэтому теперь заказ уходит
  // обычным HTTP-запросом с подписью initData (её бот проверяет на сервере
  // той же функцией, что и для Tarix/TOP/Profil) — работает одинаково
  // из любой точки входа.
  submitOrder(payload);
}

async function submitOrder(payload) {
  const errorEl = document.getElementById("modal-error");
  const payBtn = document.querySelector('[onclick="sendPaymentInfo()"]');
  const base = await getShopApiUrl();

  if (!base || !tg || !tg.initData) {
    orderInFlight = false;
    if (tg && tg.sendData) {
      // Резервный путь на случай, если публичный API ещё не настроен
      // (SHOP_API_URL пустой) — старый способ хотя бы не роняет заказ совсем.
      // Telegram сам закрывает WebApp после sendData() — это его поведение,
      // мы это не контролируем.
      tg.sendData(JSON.stringify(payload));
      tg.close();
    } else {
      alert("DEMO (Telegram ichida ochish kerak): " + JSON.stringify(payload, null, 2));
    }
    return;
  }

  errorEl.classList.add("hidden");
  orderInFlight = true;
  const prevBtnHtml = payBtn ? payBtn.innerHTML : null;
  if (payBtn) {
    payBtn.disabled = true;
    payBtn.innerHTML = '<span class="inline-block w-4 h-4 border-2 border-white/40 border-t-white rounded-full align-middle" style="animation: spin .7s linear infinite;"></span>';
  }

  try {
    // БЫЛО: /public/create_order — бот присылал в ЧАТ вопрос «Всё верно?»,
    // и покупка обрывалась на середине: человек должен был выйти из витрины
    // в переписку. Теперь заказ создаётся сразу, а витрина сама ведёт клиента
    // по этапам (оплата -> проверка -> выполнение -> готово).
    const res = await fetch(base + "/public/place_order", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: tg.initData, payload: payload }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      errorEl.textContent = data.error === "no_username" ? t("cart_err_no_username")
        : (data.error || "Xatolik yuz berdi, qayta urinib ko'ring.");
      errorEl.classList.remove("hidden");
      return;
    }
    openOrderFlow({ order_id: data.order_id }, {
      order_id: data.order_id,
      item_name: data.item_name || payload.item_name,
      recipient: data.recipient || payload.recipient,
      price_uzs: data.price_uzs,
      pay_amount: data.pay_amount,
      card_number: data.card_number,
      card_holder: data.card_holder,
    });
  } catch (e) {
    errorEl.textContent = "Server bilan bog'lanib bo'lmadi, qayta urinib ko'ring.";
    errorEl.classList.remove("hidden");
  } finally {
    orderInFlight = false;
    if (payBtn) {
      payBtn.disabled = false;
      payBtn.innerHTML = prevBtnHtml;
    }
  }
}

function launchSuccessConfetti() {
  const box = document.getElementById("success-confetti");
  if (!box) return;
  const colors = ["#10B981", "#D9B45B", "#2AABEE", "#8E8CD8", "#F0DFA0"];
  let html = "";
  for (let i = 0; i < 20; i++) {
    const angle = (Math.PI * 2 * i) / 20 + Math.random() * 0.3;
    const dist = 70 + Math.random() * 60;
    html += '<span class="confetti-piece" style="--tx:' + Math.round(Math.cos(angle) * dist) +
      'px; --ty:' + Math.round(Math.sin(angle) * dist) + 'px; --rot:' + Math.round((Math.random() - 0.5) * 520) +
      'deg; background:' + colors[i % colors.length] + '; animation-delay:' + Math.round(Math.random() * 120) + 'ms;"></span>';
  }
  box.innerHTML = html;
}

/* ================= ЖИВОЙ СТАТУС ЗАКАЗА =================
 * Раньше витрина показывала «заказ принят» и на этом заканчивалась: всё
 * остальное (оплата, подтверждение, выполнение) человек видел только в чате
 * бота. Теперь весь путь заказа проходит здесь — экран сам опрашивает сервер
 * и переключает этапы: ждём оплату -> проверяем чек -> выполняется -> готово.
 */
const FLOW_POLL_MS = 5000;
let flowOrder = null;      // {order_id, cart_id}
let flowStatus = null;     // последний ответ сервера
let flowSignature = null;  // отпечаток последнего отрисованного состояния
let flowTimer = null;
let flowTipTimer = null;

const FLOW_STEP_BY_STATUS = {
  awaiting_payment: 1, payment_review: 2, paid: 3, fulfilling: 3, completed: 4, rejected: 0,
};

function openOrderFlow(ref, optimistic) {
  flowOrder = { order_id: ref.order_id || null, cart_id: ref.cart_id || null };
  flowSignature = null;
  closeModal();
  document.getElementById("order-flow-screen").classList.remove("hidden");

  // Первый кадр рисуем сразу из того, что уже знает витрина, чтобы экран не
  // мигал пустотой, пока летит первый запрос статуса.
  if (optimistic) {
    flowStatus = Object.assign({ status: "awaiting_payment", items: [] }, optimistic);
    renderOrderFlow();
  }
  pollOrderFlow();
  startFlowPolling();
}

function closeOrderFlow() {
  stopFlowPolling();
  flowOrder = null;
  document.getElementById("order-flow-screen").classList.add("hidden");
  refreshActiveOrder();
}

function startFlowPolling() {
  stopFlowPolling();
  flowTimer = setInterval(pollOrderFlow, FLOW_POLL_MS);
}

function stopFlowPolling() {
  if (flowTimer) { clearInterval(flowTimer); flowTimer = null; }
  if (flowTipTimer) { clearInterval(flowTipTimer); flowTipTimer = null; }
}

async function pollOrderFlow() {
  if (!flowOrder) return;
  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) return;

  try {
    const res = await fetch(base + "/public/order_status", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData, order_id: flowOrder.order_id, cart_id: flowOrder.cart_id }),
    });
    const data = await res.json();
    if (!data.ok) return;  // заказ ещё не виден/не найден — попробуем на следующем круге

    // Перерисовываем экран ТОЛЬКО когда что-то реально изменилось: иначе
    // каждые 5 секунд пересобирался бы блок действий — моргала бы анимация,
    // а у человека могло бы "выпрыгнуть" из-под пальца поле или кнопка.
    const sig = [data.status, data.needs_rent_link, data.price_uzs, data.item_name, data.admin_comment].join("|");
    const statusChanged = flowSignature !== null && flowSignature !== sig;
    const first = flowSignature === null;
    flowSignature = sig;
    flowStatus = data;
    if (!flowOrder.cart_id && data.cart_id) flowOrder.cart_id = data.cart_id;
    if (statusChanged || first) renderOrderFlow(!first);

    // Заказ дошёл до конца — больше опрашивать нечего
    if (data.status === "completed" || data.status === "rejected") stopFlowPolling();
  } catch (e) { /* сеть моргнула — следующий круг опроса попробует снова */ }
}

/** Кружок этапа: пройденный, текущий (пульсирует) или будущий. */
function flowStepsHTML(step) {
  const labels = [t("flow_step_created"), t("flow_step_payment"), t("flow_step_doing"), t("flow_step_done")];
  return labels.map(function(label, i) {
    const n = i + 1;
    const done = step > n;
    const current = step === n;
    const dot = done
      ? '<span class="w-5 h-5 rounded-full bg-emerald-500 text-white text-[10px] font-bold flex items-center justify-center">✓</span>'
      : current
        ? '<span class="w-5 h-5 rounded-full bg-neon-blue text-white text-[10px] font-bold flex items-center justify-center animate-pulse">' + n + '</span>'
        : '<span class="w-5 h-5 rounded-full bg-white/[0.08] text-gray-500 text-[10px] font-bold flex items-center justify-center">' + n + '</span>';
    const line = i < labels.length - 1
      ? '<span class="flex-1 h-[2px] ' + (step > n ? "bg-emerald-500" : "bg-white/10") + ' mx-1"></span>'
      : "";
    return '<div class="flex items-center ' + (i < labels.length - 1 ? "flex-1" : "") + '">' +
      '<div class="flex flex-col items-center gap-1">' + dot +
        '<span class="text-[8px] ' + (current ? "text-neon-blue font-semibold" : "text-gray-500") + ' whitespace-nowrap">' + label + '</span>' +
      '</div>' + line +
    '</div>';
  }).join("");
}

const FLOW_VISUAL = {
  check: '<div id="success-confetti" class="absolute inset-0"></div>' +
    '<div class="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center relative" style="animation: successPop .5s cubic-bezier(.2,1.4,.4,1) both; box-shadow: 0 0 36px -4px rgba(16,185,129,0.6);">' +
      '<svg width="36" height="36" viewBox="0 0 24 24" fill="none">' +
        '<path d="M4 12.5L9.5 18L20 6" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" ' +
              'stroke-dasharray="26" stroke-dashoffset="26" style="animation: drawCheck .4s ease-out .25s forwards;"/>' +
      '</svg>' +
    '</div>',
  waiting: '<div class="w-20 h-20 rounded-full bg-white/[0.06] border border-white/10 flex items-center justify-center relative">' +
      '<span class="absolute inset-0 rounded-full border-2 border-neon-blue/50 pulse-ring"></span>' +
      '<span class="text-3xl">💳</span>' +
    '</div>',
  // Крутящееся кольцо + эмодзи внутри: видно, что процесс идёт
  spinner: function(emoji) {
    return '<div class="w-20 h-20 rounded-full flex items-center justify-center relative">' +
        '<span class="absolute inset-0 rounded-full border-[3px] border-white/10 border-t-neon-blue" style="animation: spin 1s linear infinite;"></span>' +
        '<span class="absolute inset-0 rounded-full border-2 border-neon-blue/40 pulse-ring"></span>' +
        '<span class="text-3xl">' + emoji + '</span>' +
      '</div>';
  },
  failed: '<div class="w-20 h-20 rounded-full bg-red-500/15 border border-red-500/40 flex items-center justify-center">' +
      '<span class="text-3xl">✕</span>' +
    '</div>',
};

function renderOrderFlow(statusChanged) {
  const s = flowStatus;
  if (!s) return;
  const visual = document.getElementById("flow-visual");
  const titleEl = document.getElementById("flow-title");
  const subEl = document.getElementById("flow-subtitle");
  const actionEl = document.getElementById("flow-action");
  const buttonsEl = document.getElementById("flow-buttons");

  document.getElementById("success-item").textContent = s.item_name || "—";
  document.getElementById("success-recipient").textContent =
    s.recipient && s.recipient.charAt(0) === "@" ? s.recipient : t("cart_to_self");
  document.getElementById("success-price").textContent = fmtUZS(s.price_uzs || 0);
  document.getElementById("flow-steps").innerHTML = flowStepsHTML(FLOW_STEP_BY_STATUS[s.status] || 1);

  if (flowTipTimer) { clearInterval(flowTipTimer); flowTipTimer = null; }

  if (s.status === "completed") {
    visual.innerHTML = FLOW_VISUAL.check;
    titleEl.textContent = t("flow_done_title");
    titleEl.className = "text-[19px] font-bold mb-1 text-emerald-400";
    subEl.textContent = t("flow_done_sub");
    actionEl.innerHTML = "";
    buttonsEl.innerHTML =
      '<button onclick="flowBuyMore()" class="w-full py-3.5 rounded-2xl btn-primary press font-semibold text-white text-sm mb-2.5">' + t("order_success_more") + '</button>' +
      '<button onclick="flowGoTarix()" class="w-full py-3.5 rounded-2xl pill press font-semibold text-sm mb-2.5">' + t("order_success_history") + '</button>' +
      '<button onclick="closeOrderFlow()" class="w-full py-3 text-gray-400 text-xs">' + t("order_success_home") + '</button>';
    launchSuccessConfetti();
    if (statusChanged && tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    return;
  }

  if (s.status === "rejected") {
    visual.innerHTML = FLOW_VISUAL.failed;
    titleEl.textContent = t("flow_rejected_title");
    titleEl.className = "text-[19px] font-bold mb-1 text-red-400";
    subEl.textContent = s.admin_comment || t("flow_rejected_sub");
    actionEl.innerHTML = "";
    buttonsEl.innerHTML =
      '<button onclick="flowBuyMore()" class="w-full py-3.5 rounded-2xl btn-primary press font-semibold text-white text-sm mb-2.5">' + t("order_success_more") + '</button>' +
      '<button onclick="flowWriteOperator()" class="w-full py-3.5 rounded-2xl pill press font-semibold text-sm">' + t("flow_write_operator") + '</button>';
    return;
  }

  titleEl.className = "text-[19px] font-bold mb-1";

  if (s.status === "awaiting_payment") {
    visual.innerHTML = FLOW_VISUAL.waiting;
    titleEl.textContent = t("flow_awaiting_title");
    subEl.textContent = t("flow_awaiting_sub");
    // Точная сумма к переводу + предупреждение про комиссию банка: если банк
    // удержит её из перевода, на карту придёт меньше и автоподтверждение не
    // сработает — человек должен узнать об этом ДО оплаты, а не после.
    // Блок с точной суммой показываем ВСЕГДА, даже если она совпала с ценой:
    // человек должен видеть, сколько именно перевести, и предупреждение про
    // комиссию банка. Раньше блок появлялся только при уникальной сумме — и
    // без неё предупреждения не было вообще.
    const exact = s.pay_amount
      ? '<div class="rounded-2xl p-3 mb-3 text-left" style="background: rgba(217,180,91,0.10); border: 1px solid rgba(217,180,91,0.35);">' +
          '<div class="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">' + t("flow_pay_exact") + '</div>' +
          '<div class="text-[19px] font-black text-neon-yellow leading-none mb-2">' + fmtUZS(s.pay_amount) + '</div>' +
          '<div class="text-[11px] text-gray-300 leading-snug">⚠️ ' + t("flow_commission_note") + '</div>' +
        '</div>'
      : "";
    actionEl.innerHTML =
      '<div class="glass-card rounded-2xl p-3.5 mb-3 text-left">' +
        '<div class="text-[9px] text-gray-500 mb-0.5">' + t("modal_card_label") + '</div>' +
        '<div class="text-[15px] font-mono font-bold text-white tracking-wider mb-1.5">' + (s.card_number || "—") + '</div>' +
        '<div class="flex justify-between items-end">' +
          '<div><div class="text-[9px] text-gray-500">' + t("modal_card_holder_label") + '</div>' +
          '<div class="text-[11px]">' + (s.card_holder || "—") + '</div></div>' +
          '<button onclick="copyActiveCard(\'' + (s.card_number || "") + '\')" class="press bg-neon-blue/15 text-neon-blue px-3 py-1.5 rounded-lg text-[10px] font-semibold">' + t("modal_copy") + '</button>' +
        '</div>' +
      '</div>' +
      exact +
      '<input type="file" id="flow-receipt-input" accept="image/*" class="hidden" onchange="flowSubmitReceipt()" />' +
      '<button onclick="document.getElementById(\'flow-receipt-input\').click()" id="flow-receipt-btn" class="press w-full py-3.5 rounded-2xl btn-primary font-semibold text-white text-sm">📎 ' + t("ao_pay_upload") + '</button>' +
      '<p id="flow-receipt-error" class="hidden text-red-400 text-[11px] mt-2"></p>';
    buttonsEl.innerHTML =
      '<button onclick="flowCancelOrder()" class="w-full py-3 rounded-2xl pill press text-[12px] text-gray-400 mb-2">' + t("ao_cancel") + '</button>' +
      '<button onclick="closeOrderFlow()" class="w-full py-3 text-gray-400 text-xs">' + t("flow_minimize") + '</button>';
    return;
  }

  if (s.status === "payment_review") {
    visual.innerHTML = FLOW_VISUAL.spinner("🔍");
    titleEl.textContent = t("flow_review_title");
    subEl.textContent = t("flow_review_sub");
    actionEl.innerHTML = "";
    buttonsEl.innerHTML = '<button onclick="closeOrderFlow()" class="w-full py-3 text-gray-400 text-xs">' + t("flow_minimize") + '</button>';
    return;
  }

  // paid / fulfilling — «выполняется»: анимация + сменяющиеся пояснения,
  // чтобы ожидание не выглядело как зависший экран
  visual.innerHTML = FLOW_VISUAL.spinner("⚙️");
  titleEl.textContent = t("flow_doing_title");
  subEl.textContent = t("flow_doing_sub");

  const linkBlock = s.needs_rent_link
    ? '<div class="glass-card rounded-2xl p-3.5 text-left mb-3">' +
        '<div class="text-[12px] font-semibold text-white mb-1">🔗 ' + t("ao_link_title") + '</div>' +
        '<div class="text-[11px] text-gray-400 mb-2.5 leading-snug">' + t("ao_link_hint") + '</div>' +
        '<input id="rent-link-input" type="text" placeholder="tc://..." class="w-full bg-white/[0.04] border border-white/[0.09] rounded-xl px-3 py-2.5 text-[11px] text-white focus:outline-none focus:border-neon-blue/60 mb-2" />' +
        '<p id="rent-link-error" class="hidden text-red-400 text-[11px] mb-2"></p>' +
        '<button onclick="submitRentLink()" id="rent-link-btn" class="press w-full py-3 rounded-xl btn-primary font-semibold text-white text-[13px]">' + t("ao_link_send") + '</button>' +
      '</div>'
    : "";

  actionEl.innerHTML =
    linkBlock +
    '<div class="glass-card rounded-2xl p-3 flex items-center gap-2.5 text-left">' +
      '<span class="w-4 h-4 border-2 border-white/20 border-t-neon-blue rounded-full flex-shrink-0" style="animation: spin .8s linear infinite;"></span>' +
      '<span id="flow-tip" class="text-[11.5px] text-gray-300 transition-opacity duration-300"></span>' +
    '</div>';
  buttonsEl.innerHTML = '<button onclick="closeOrderFlow()" class="w-full py-3 text-gray-400 text-xs">' + t("flow_minimize") + '</button>';

  const tips = t("flow_tips") || [];
  const tipEl = document.getElementById("flow-tip");
  let tipIndex = 0;
  function paintTip() {
    if (!tipEl || !tips.length) return;
    tipEl.style.opacity = 0;
    setTimeout(function() {
      tipEl.textContent = tips[tipIndex % tips.length];
      tipEl.style.opacity = 1;
      tipIndex++;
    }, 250);
  }
  paintTip();
  flowTipTimer = setInterval(paintTip, 3000);
}

/**
 * Сжимает фото чека перед отправкой.
 *
 * Зачем: фото с телефона весит 3-6 МБ, а в base64 — ещё на треть больше.
 * Такой запрос и по мобильному интернету идёт долго, и упирается в лимиты
 * сервера (именно на этом чеки и обрывались с "bad request body"). Для чтения
 * суммы на чеке хватает картинки в 1600px и JPEG-качества 0.8 — это обычно
 * 200-400 КБ, то есть в 10-20 раз меньше.
 *
 * Если браузер по какой-то причине не смог перерисовать картинку (редкий
 * формат, нет памяти) — возвращаем null, и файл уйдёт как есть.
 */
function compressReceipt(file, maxSide, quality) {
  return new Promise(function(resolve) {
    let url;
    try { url = URL.createObjectURL(file); } catch (e) { resolve(null); return; }

    const img = new Image();
    img.onload = function() {
      try {
        const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
        const w = Math.max(1, Math.round(img.width * scale));
        const h = Math.max(1, Math.round(img.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        canvas.getContext("2d").drawImage(img, 0, 0, w, h);
        const dataUrl = canvas.toDataURL("image/jpeg", quality);
        URL.revokeObjectURL(url);
        resolve(dataUrl.indexOf(",") > 0 ? dataUrl.split(",")[1] : null);
      } catch (e) {
        URL.revokeObjectURL(url);
        resolve(null);
      }
    };
    img.onerror = function() { URL.revokeObjectURL(url); resolve(null); };
    img.src = url;
  });
}

/** Читает файл как base64 без сжатия — запасной путь. */
function readFileBase64(file) {
  return new Promise(function(resolve, reject) {
    const r = new FileReader();
    r.onload = function() { resolve(String(r.result).split(",")[1]); };
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

/** Готовит чек к отправке: сначала пробуем сжать, иначе — как есть. */
async function receiptToBase64(file) {
  const compressed = await compressReceipt(file, 1600, 0.8);
  if (compressed) return compressed;
  return await readFileBase64(file);
}

async function flowSubmitReceipt() {
  const input = document.getElementById("flow-receipt-input");
  const btn = document.getElementById("flow-receipt-btn");
  const errorEl = document.getElementById("flow-receipt-error");
  if (!input || !input.files || !input.files[0] || !flowStatus) return;

  const file = input.files[0];
  errorEl.classList.add("hidden");
  if (file.size > 25 * 1024 * 1024) {
    errorEl.textContent = t("ao_err_too_big"); errorEl.classList.remove("hidden"); return;
  }

  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) return;

  const prev = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="inline-block w-4 h-4 border-2 border-white/40 border-t-white rounded-full align-middle" style="animation: spin .7s linear infinite;"></span>';

  try {
    const base64 = await receiptToBase64(file);
    const res = await fetch(base + "/public/submit_receipt", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData, order_id: flowStatus.order_id, image_base64: base64 }),
    });
    const data = await res.json();
    if (data.ok) {
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      pollOrderFlow();          // сразу перерисуем экран в «проверяем оплату»
      startFlowPolling();
    } else {
      const reasons = {
        wrong_status: t("ao_err_wrong_status"), too_big: t("ao_err_too_big"),
        no_image: t("ao_err_no_image"), bad_image: t("ao_err_no_image"), not_found: t("ao_err_not_found"),
      };
      errorEl.textContent = reasons[data.error] || (t("ao_err_receipt") + " (" + (data.error || res.status) + ")");
      errorEl.classList.remove("hidden");
    }
  } catch (e) {
    errorEl.textContent = t("ao_err_network"); errorEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerHTML = prev;
    input.value = "";
  }
}

function flowCancelOrder() {
  if (!flowStatus) return;
  askConfirm(t("ao_cancel_confirm"), async function() {
    const base = await getShopApiUrl();
    const initData = await waitForInitData();
    if (!base || !initData) return;
    try {
      await fetch(base + "/public/cancel_order", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData: initData, order_id: flowStatus.order_id }),
      });
    } catch (e) { /* молча — статус всё равно перечитаем ниже */ }
    pollOrderFlow();
  });
}

function flowWriteOperator() {
  closeOrderFlow();
  switchTab("profil");
}

function flowGoTarix() {
  closeOrderFlow();
  switchTab("tarix");
}

function flowBuyMore() {
  closeOrderFlow();
  switchTab("asosiy");
}

/* ---------------- Профиль / рефералка / условия аренды ---------------- */
async function initProfile() {
  // БАГ БЫЛ ЗДЕСЬ: ждали именно подписанную initData (нужна только для
  // /public/my_orders и /public/my_stats), а initDataUnsafe.user — отдельные,
  // неподписанные данные, которые обычно готовы раньше. Из-за завязки на
  // не тот таймер имя/аватар иногда так и оставались плейсхолдером "—",
  // даже когда сам Telegram уже готов был отдать данные пользователя.
  const u = await waitForUnsafeUser();
  if (!u) {
    // После ожидания юзера всё ещё нет — редкий случай (например, открыли
    // не из настоящего Telegram-клиента). Тихо оставляем плейсхолдер.
    return;
  }
  document.getElementById("profile-name").textContent = u.first_name || "Mijoz";
  document.getElementById("profile-username").textContent = u.username ? "@" + u.username : "";
  document.getElementById("profile-id").textContent = "ID: " + u.id;
  document.getElementById("profile-avatar").textContent = (u.first_name ? u.first_name.charAt(0) : "?").toUpperCase();
}

/* ---------------- API бота-магазина (Tarix/TOP/Profil) ---------------- */
let shopApiUrl = null;
async function getShopApiUrl() {
  if (shopApiUrl !== null) return shopApiUrl;
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    shopApiUrl = data.shop_api_url || "";
  } catch (e) {
    shopApiUrl = "";
  }
  return shopApiUrl;
}

const CATEGORY_EMOJI = { stars: "\u2b50", premium: "\ud83d\udc8e", simple_gift: "\ud83c\udf81", nft_rent: "\ud83d\uddbc" };
const STATUS_KEY = {
  awaiting_payment: "status_awaiting_payment", payment_review: "status_payment_review",
  paid: "status_paid", fulfilling: "status_fulfilling", completed: "status_completed", rejected: "status_rejected",
};

function formatOrderDate(sqlDate) {
  if (!sqlDate) return "";
  // формат из sqlite: "YYYY-MM-DD HH:MM:SS" (UTC) — просто показываем как есть, без пересчёта пояса
  return sqlDate.replace("T", " ").slice(0, 16);
}

async function renderHistory() {
  const listEl = document.getElementById("tarix-list");
  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) {
    listEl.innerHTML =
      '<div class="glass-card rounded-[22px] p-6 text-center text-gray-400">' +
      '<p class="text-3xl mb-2">\ud83d\uded2</p><p class="text-sm">' + t("history_open_bot") + '</p></div>';
    return;
  }
  listEl.innerHTML = '<div class="text-center text-xs text-gray-500 py-6">' + t("history_loading") + '</div>';

  try {
    const res = await fetch(base + "/public/my_orders", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData }),
    });
    const data = await res.json();
    const orders = data.orders || [];

    if (!orders.length) {
      listEl.innerHTML =
        '<div class="glass-card rounded-[22px] p-6 text-center text-gray-400">' +
        '<p class="text-3xl mb-2">\ud83d\uded2</p><p class="text-sm">' + t("history_empty") + '</p></div>';
      return;
    }

    listEl.innerHTML = orders.map(function(o) {
      const emoji = CATEGORY_EMOJI[o.category] || "\ud83d\udce6";
      const statusLabel = t(STATUS_KEY[o.status] || o.status);
      const statusColor = (o.status === "completed") ? "text-green-400" : (o.status === "rejected") ? "text-red-400" : "text-gray-400";
      return '<div class="glass-card rounded-2xl p-3.5 flex items-center justify-between gap-2">' +
        '<div class="flex items-center gap-2.5 min-w-0">' +
          '<span class="text-xl flex-shrink-0">' + emoji + '</span>' +
          '<div class="min-w-0">' +
            '<div class="text-xs font-semibold text-white truncate">' + o.item_name + '</div>' +
            '<div class="text-[10px] ' + statusColor + '">' + statusLabel + ' \u00b7 ' + formatOrderDate(o.created_at) + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="text-xs font-bold text-neon-blue flex-shrink-0">' + fmtUZS(o.price_uzs) + '</div>' +
      '</div>';
    }).join("");
  } catch (e) {
    listEl.innerHTML =
      '<div class="glass-card rounded-[22px] p-6 text-center text-gray-400">' +
      '<p class="text-sm">' + t("history_empty") + '</p></div>';
  }
}

let currentTopPeriod = "all";
function setTopPeriod(period) {
  currentTopPeriod = period;
  ["today","week","month","all"].forEach(function(p) {
    const btn = document.getElementById("top-period-" + p);
    if (!btn) return;
    btn.className = p === period
      ? "press px-3.5 py-2 rounded-full pill-gold text-[11px] font-semibold whitespace-nowrap"
      : "press px-3.5 py-2 rounded-full pill text-[11px] whitespace-nowrap";
  });
  renderLeaderboard(period);
}

/** Небольшой салют вокруг короны 1-го места в рейтинге — чисто декоративно. */
/**
 * Салют с двух сторон подиума — летит от левого и правого края навстречу
 * центру (как на награждении), а не просто разлетается вокруг короны.
 */
function launchConfetti() {
  const colors = ["#D9B45B", "#2AABEE", "#8E8CD8", "#5AC8FA", "#F0DFA0"];

  function burst(boxId, dirX) {
    const box = document.getElementById(boxId);
    if (!box) return;
    let html = "";
    for (let i = 0; i < 14; i++) {
      // dirX задаёт общее направление (влево/вправо), с разбросом по вертикали
      const spread = (Math.random() - 0.5) * 70;
      const dist = 60 + Math.random() * 50;
      const tx = Math.round(dirX * dist);
      const ty = Math.round(spread - 30 - Math.random() * 20);
      const rot = Math.round((Math.random() - 0.5) * 520);
      const color = colors[i % colors.length];
      const delay = Math.round(Math.random() * 140);
      html += '<span class="confetti-piece" style="--tx:' + tx + 'px; --ty:' + ty + 'px; --rot:' + rot + 'deg; background:' + color + '; animation-delay:' + delay + 'ms;"></span>';
    }
    box.innerHTML = html;
  }

  burst("podium-confetti-left", 1);   // летит вправо, к центру
  burst("podium-confetti-right", -1); // летит влево, к центру
}

async function renderLeaderboard(period) {
  const listEl = document.getElementById("top-list");
  const base = await getShopApiUrl();
  if (!base) {
    listEl.innerHTML =
      '<div class="glass-card rounded-[22px] p-6 text-center text-gray-400">' +
      '<p class="text-3xl mb-2">\ud83c\udfc6</p><p class="text-sm font-semibold text-white mb-1">' + t("top_forming") + '</p>' +
      '<p class="text-xs">' + t("top_hint") + '</p></div>';
    return;
  }
  listEl.innerHTML = '<div class="text-center text-xs text-gray-500 py-6">' + t("history_loading") + '</div>';

  const myUser = await waitForUnsafeUser();
  const myId = myUser ? myUser.id : null;

  try {
    const res = await fetch(base + "/public/leaderboard?period=" + period);
    const data = await res.json();
    const rows = data.leaderboard || [];

    if (!rows.length) {
      listEl.innerHTML =
        '<div class="glass-card rounded-[22px] p-6 text-center text-gray-400">' +
        '<p class="text-3xl mb-2">\ud83c\udfc6</p><p class="text-sm font-semibold text-white mb-1">' + t("top_forming") + '</p>' +
        '<p class="text-xs">' + t("top_hint") + '</p></div>';
      return;
    }

    const initials = function(name) { return (name || "?").trim().charAt(0).toUpperCase(); };

    function personName(r) {
      return r.full_name || (r.username ? "@" + r.username : "ID " + r.user_id);
    }

    // Подиум для топ-3: 2 место слева, 1 (приподнятое, с короной) в центре,
    // 3 справа — у каждого места свой цвет авы под цвет медали, не одинаковый
    // градиент для всех, плюс плавное появление при заходе на вкладку.
    let podiumHtml = "";
    if (rows.length >= 1) {
      const order = [1, 0, 2].filter(function(i) { return rows[i]; }); // 2-1-3 визуально
      const AVATAR_BG = {
        0: "background: radial-gradient(circle at 30% 25%, #F3D98A, #D9A93B 70%);",
        1: "background: radial-gradient(circle at 30% 25%, #D7DCE2, #9AA3AD 70%);",
        2: "background: radial-gradient(circle at 30% 25%, #E3A567, #B5713A 70%);",
      };
      const RING = {
        0: "ring-2 ring-neon-yellow", 1: "ring-2 ring-gray-300/70", 2: "ring-2 ring-amber-700/60",
      };
      const GLOW = { 0: "0 0 26px -2px rgba(217,180,91,0.65)", 1: "0 0 16px -4px rgba(200,205,212,0.4)", 2: "0 0 16px -4px rgba(181,113,58,0.4)" };
      const SIZE = { 0: "w-[72px] h-[72px] text-2xl -mt-9", 1: "w-14 h-14 text-lg -mt-7", 2: "w-14 h-14 text-lg -mt-7" };
      // Настоящие блоки пьедестала — разной высоты (1 место выше всех),
      // с крупным номером, как на олимпийском подиуме.
      const BLOCK_H = { 0: "h-24", 1: "h-16", 2: "h-12" };
      const BLOCK_BG = {
        0: "background: linear-gradient(180deg, #F3D98A 0%, #C99A3E 100%);",
        1: "background: linear-gradient(180deg, #E3E7EC 0%, #9AA3AD 100%);",
        2: "background: linear-gradient(180deg, #E3A567 0%, #A9713C 100%);",
      };
      const BLOCK_NUM_COLOR = { 0: "#6b4e11", 1: "#4a5058", 2: "#5c3a17" };
      podiumHtml =
        '<div class="relative overlay-enter">' +
          '<div id="podium-confetti-left" class="absolute left-2 top-8 w-0 h-0"></div>' +
          '<div id="podium-confetti-right" class="absolute right-2 top-8 w-0 h-0"></div>' +
          '<div class="flex items-end justify-center gap-2.5 pt-1 pb-2">' +
          order.map(function(i, idx) {
            const r = rows[i];
            const name = personName(r);
            const isMe = myId && r.user_id === myId;
            return '<div class="flex flex-col items-center w-[92px]" style="animation: sheetUp .4s cubic-bezier(.2,.9,.25,1) both; animation-delay:' + (idx * 70) + 'ms;">' +
              (i === 0 ? '<div class="text-2xl mb-1" style="animation: float 2.4s ease-in-out infinite;">👑</div>' : '<div class="h-8"></div>') +
              '<div class="relative z-10">' +
                '<div class="' + SIZE[i] + ' rounded-full ' + RING[i] + ' flex items-center justify-center font-bold text-white' + (isMe ? " outline outline-2 outline-neon-blue outline-offset-2" : "") + '" style="' + AVATAR_BG[i] + ' box-shadow:' + GLOW[i] + ';">' + initials(name) + '</div>' +
              '</div>' +
              '<div class="text-[11.5px] font-semibold text-white mt-2 max-w-[90px] truncate text-center px-1">' + name + '</div>' +
              '<div class="text-[11px] font-bold text-neon-yellow mb-2">' + fmtUZS(r.total_uzs) + '</div>' +
              '<div class="w-full ' + BLOCK_H[i] + ' rounded-t-xl flex items-start justify-center pt-1.5 shadow-[0_-2px_10px_rgba(0,0,0,0.25)]" style="' + BLOCK_BG[i] + '">' +
                '<span class="text-2xl font-black" style="color:' + BLOCK_NUM_COLOR[i] + '">' + (i + 1) + '</span>' +
              '</div>' +
            '</div>';
          }).join("") +
          '</div>' +
        '</div>';
    }

    const restHtml = rows.slice(3).map(function(r, idx) {
      const i = idx + 3;
      const name = personName(r);
      const isMe = myId && r.user_id === myId;
      return '<div class="press flex items-center justify-between gap-2 rounded-2xl p-3.5 ' +
        (isMe ? "bg-neon-blue/10 border border-neon-blue/40" : "glass-card") + '">' +
        '<div class="flex items-center gap-3 min-w-0">' +
          '<span class="text-[11px] font-bold text-gray-500 w-6 h-6 rounded-full bg-white/[0.06] flex items-center justify-center flex-shrink-0">' + (i + 1) + '</span>' +
          '<div class="min-w-0">' +
            '<div class="text-xs font-semibold text-white truncate">' + name + (isMe ? ' \u00b7 <span class="text-neon-blue">' + t("top_you") + '</span>' : '') + '</div>' +
            '<div class="text-[10px] text-gray-400">' + r.orders_count + ' ' + t("top_orders_suffix") + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="text-xs font-bold text-neon-yellow flex-shrink-0">' + fmtUZS(r.total_uzs) + '</div>' +
      '</div>';
    }).join("");

    listEl.innerHTML = podiumHtml + '<div class="space-y-2">' + restHtml + '</div>';
    launchConfetti();
  } catch (e) {
    listEl.innerHTML = '<div class="text-center text-xs text-gray-500 py-6">' + t("top_empty") + '</div>';
  }
}

async function renderProfileStats() {
  const box = document.getElementById("profile-stats-box");
  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) { box.classList.add("hidden"); return; }

  try {
    const res = await fetch(base + "/public/my_stats", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData }),
    });
    const stats = await res.json();

    const catRows = Object.keys(CATEGORY_EMOJI).map(function(cat) {
      const amount = (stats.by_category || {})[cat] || 0;
      if (!amount) return "";
      return '<div class="flex justify-between items-center text-xs py-1.5 border-b border-white/5 last:border-0">' +
        '<span class="text-gray-300">' + t("cat_" + cat) + '</span>' +
        '<span class="font-semibold text-white">' + fmtUZS(amount) + '</span></div>';
    }).join("");

    box.classList.remove("hidden");
    const hasPurchases = (stats.total_uzs || 0) > 0;
    box.innerHTML =
      // Крупная сумма как герой блока — раньше "Jami xarid" терялся мелким
      // текстом в строке и выглядел пустым у новых клиентов.
      '<div class="text-center pb-3">' +
        '<div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">' + t("profile_stats_total") + '</div>' +
        '<div class="text-[26px] font-black text-white leading-none tracking-tight">' + fmtUZS(stats.total_uzs || 0) + '</div>' +
        (stats.rank
          ? '<div class="inline-flex items-center gap-1.5 mt-2.5 pill-gold px-3 py-1 rounded-full text-[10px] font-bold">' +
              '<span>🏆</span><span>' + t("profile_stats_rank") + ' #' + stats.rank + '</span>' +
            '</div>'
          : '<div class="text-[11px] text-gray-500 mt-2">' + t("profile_no_purchases") + '</div>') +
      '</div>' +
      (hasPurchases ? '<div class="pt-3 border-t border-white/[0.08] space-y-0.5">' + catRows + '</div>' : '');
  } catch (e) {
    box.classList.add("hidden");
  }
}

async function renderRentTerms() {
  try {
    const res = await fetch("/api/rent_terms");
    const d = await res.json();
    document.getElementById("rent-terms-text").textContent = t("rent_terms")(fmtUZS(d.fee_uzs), fmtUZS(d.refund_uzs));
  } catch (e) { /* тихо игнорируем */ }
}

/* ---------------- Init ---------------- */
/**
 * Тихая диагностика — НЕ показывается пользователю (это была ошибка в
 * прошлый раз с текстом "DEBUG: ..."). Просто один раз отправляет на сервер
 * реальную картину того, что видит этот конкретный телефон: есть ли вообще
 * window.Telegram.WebApp, дождались ли initData/initDataUnsafe.user, сколько
 * это заняло, какая платформа/версия Telegram. Смотрится потом в логах
 * Railway — так можно найти причину точно, а не гадать по скриншотам.
 */
async function sendDiag() {
  const base = await getShopApiUrl();
  if (!base) return;
  const t0 = Date.now();
  const initData = await waitForInitData();
  const user = await waitForUnsafeUser();
  try {
    await fetch(base + "/public/_diag", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tg_exists: !!tg,
        platform: tg ? tg.platform : null,
        version: tg ? tg.version : null,
        initData_len: initData ? initData.length : 0,
        unsafe_user_exists: !!user,
        unsafe_user_id: user ? user.id : null,
        wait_ms: Date.now() - t0,
        ua: navigator.userAgent,
      }),
    });
  } catch (e) { /* тихо игнорируем — это диагностика, не критично */ }
}

applyI18n();
initProfile();
initSupportInfo();
initLiveFeed();
sendDiag();
// Аренды тянем на старте, а не только при заходе на вкладку: если срок
// заканчивается сегодня, человек должен увидеть это сразу.
renderMyRentals();

/* ---------------- Живая лента заказов ---------------- */
function timeAgoLabel(ts) {
  const diffMin = Math.max(1, Math.round((Date.now() / 1000 - ts) / 60));
  if (diffMin < 60) return diffMin + " " + t("minutes_ago");
  const diffH = Math.round(diffMin / 60);
  return diffH + " " + t("hours_ago");
}

async function initLiveFeed() {
  let items = [];
  try {
    const res = await fetch("/api/live_feed");
    items = await res.json();
  } catch (e) { return; }

  if (!items.length) return;

  const bar = document.getElementById("live-feed-bar");
  const textEl = document.getElementById("live-feed-text");
  bar.classList.remove("hidden");

  let i = 0;
  function paint() {
    const it = items[i % items.length];
    textEl.style.opacity = 0;
    setTimeout(function() {
      textEl.textContent = it.emoji + " " + it.label + " · " + timeAgoLabel(it.ts);
      textEl.style.opacity = 1;
    }, 250);
    i++;
  }
  paint();
  setInterval(paint, 3500);
}

/* ================= Как работает аренда (пошагово) ================= */
function toggleRentHowto() {
  const box = document.getElementById("rent-howto");
  const arrow = document.getElementById("howto-arrow");
  const opening = box.classList.contains("hidden");
  if (opening && !box.innerHTML) {
    box.innerHTML = (t("howto_steps") || []).map(function(step, i) {
      return '<div class="glass-card rounded-2xl p-3 flex items-start gap-3" ' +
        'style="animation: sheetUp .3s cubic-bezier(.2,.9,.25,1) both; animation-delay:' + (i * 40) + 'ms;">' +
        '<span class="w-6 h-6 rounded-full bg-neon-blue/15 text-neon-blue text-[10px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">' + (i + 1) + '</span>' +
        '<span class="text-[12px] text-gray-300 leading-snug">' + step + '</span>' +
      '</div>';
    }).join("");
  }
  box.classList.toggle("hidden");
  arrow.style.transform = opening ? "rotate(180deg)" : "";
}

/* ================= Мои аренды + продление ================= */
let myRentals = [];

function rentLeftLabel(seconds) {
  if (seconds >= 86400) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    return d + " " + t("rent_days_short") + (h ? " " + h + " " + t("rent_hours_short") : "");
  }
  const h = Math.max(1, Math.floor(seconds / 3600));
  return h + " " + t("rent_hours_short");
}

async function renderMyRentals() {
  const box = document.getElementById("my-rentals-box");
  const listEl = document.getElementById("my-rentals-list");
  if (!box) return;

  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) { box.classList.add("hidden"); return; }

  try {
    const res = await fetch(base + "/public/my_rentals", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData }),
    });
    const data = await res.json();
    myRentals = data.rentals || [];
  } catch (e) { box.classList.add("hidden"); return; }

  if (!myRentals.length) { box.classList.add("hidden"); listEl.innerHTML = ""; return; }

  box.classList.remove("hidden");
  listEl.innerHTML = myRentals.map(function(r, i) {
    // Меньше суток — подсвечиваем красным: это последний момент продлить,
    // потом подарок просто исчезнет из профиля.
    const soon = r.seconds_left < 86400;
    const leftClass = soon ? "text-red-400" : "text-neon-blue";
    const extendBtn = r.can_extend
      ? '<button data-i="' + i + '" class="rent-extend-btn press pill-gold rounded-xl px-3 py-2 text-[11px] font-bold flex-shrink-0">' + t("rent_extend") + '</button>'
      : "";
    return '<div class="glass-card rounded-[20px] p-3.5 flex items-center gap-3"' +
      (soon ? ' style="border-color: rgba(248,113,113,0.45);"' : '') + '>' +
      '<div class="min-w-0 flex-1">' +
        '<div class="text-[13px] font-semibold text-white truncate">🖼 ' + r.item_name + '</div>' +
        '<div class="text-[11px] ' + leftClass + ' mt-0.5">' +
          (soon ? "⚠️ " + t("rent_ending_soon") + " · " : "") +
          t("rent_ends_in") + ": " + rentLeftLabel(r.seconds_left) +
        '</div>' +
        (r.price_per_day_uzs
          ? '<div class="text-[10px] text-gray-500 mt-0.5">' + fmtUZS(r.price_per_day_uzs) + ' · 1 ' + t("rent_days_suffix") + '</div>'
          : '') +
      '</div>' +
      extendBtn +
    '</div>';
  }).join("");

  Array.prototype.forEach.call(listEl.querySelectorAll(".rent-extend-btn"), function(btn) {
    btn.addEventListener("click", function() { openExtendModal(myRentals[Number(btn.dataset.i)]); });
  });
}

function openExtendModal(rental) {
  if (!rental) return;
  openModal({
    kind: "nft_rent_extend",
    title: t("rent_extend_title") + ": " + rental.item_name,
    price: rental.price_per_day_uzs,
    emoji: "⏳",
    raw: rental,
  });
}

/* ================= Активный заказ + ввод ссылки аренды ================= */
const ORDER_STATUS_KEY = {
  awaiting_payment: "ao_awaiting_payment",
  payment_review: "ao_payment_review",
  paid: "ao_paid",
  fulfilling: "ao_fulfilling",
};

async function refreshActiveOrder() {
  const bar = document.getElementById("active-order-bar");
  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) { bar.classList.add("hidden"); return; }

  let active = null;
  try {
    const res = await fetch(base + "/public/active_order", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData }),
    });
    const data = await res.json();
    active = data.active;
  } catch (e) { /* молча — баннер просто не покажем */ }

  if (!active) { bar.classList.add("hidden"); bar.innerHTML = ""; return; }

  const statusText = t(ORDER_STATUS_KEY[active.status] || "ao_fulfilling");
  const linkBlock = active.needs_rent_link
    ? '<div class="mt-3 pt-3 border-t border-white/[0.08]">' +
        '<div class="text-[12px] font-semibold text-white mb-1">🔗 ' + t("ao_link_title") + '</div>' +
        '<div class="text-[11px] text-gray-400 mb-2.5 leading-snug">' + t("ao_link_hint") + '</div>' +
        '<input id="rent-link-input" type="text" placeholder="tc://..." class="w-full bg-white/[0.04] border border-white/[0.09] rounded-xl px-3 py-2.5 text-[11px] text-white focus:outline-none focus:border-neon-blue/60 mb-2" />' +
        '<p id="rent-link-error" class="hidden text-red-400 text-[11px] mb-2"></p>' +
        '<button onclick="submitRentLink()" id="rent-link-btn" class="press w-full py-3 rounded-xl btn-primary font-semibold text-white text-[13px] mb-2">' + t("ao_link_send") + '</button>' +
        '<button onclick="openBotForTutorial()" class="press w-full py-2.5 rounded-xl pill text-[11px] font-medium">🎥 ' + t("ao_watch_tutorial") + '</button>' +
      '</div>'
    : "";

  // Оплата прямо в витрине: карта + загрузка чека, без ухода в чат бота
  const payBlock = active.needs_payment
    ? '<div class="mt-3 pt-3 border-t border-white/[0.08]">' +
        '<div class="text-[12px] font-semibold text-white mb-2">💳 ' + t("ao_pay_title") + '</div>' +
        '<div class="glass-card rounded-xl p-3 mb-2.5">' +
          '<div class="text-[9px] text-gray-500 mb-0.5">' + t("modal_card_label") + '</div>' +
          '<div class="text-[14px] font-mono font-bold text-white tracking-wider mb-1.5">' + (active.card_number || "—") + '</div>' +
          '<div class="flex justify-between items-end">' +
            '<div><div class="text-[9px] text-gray-500">' + t("modal_card_holder_label") + '</div>' +
            '<div class="text-[11px]">' + (active.card_holder || "—") + '</div></div>' +
            '<button onclick="copyActiveCard(\'' + (active.card_number || "") + '\')" class="press bg-neon-blue/15 text-neon-blue px-3 py-1.5 rounded-lg text-[10px] font-semibold">' + t("modal_copy") + '</button>' +
          '</div>' +
        '</div>' +
        '<div class="text-[11px] text-gray-400 mb-2 leading-snug">' + t("ao_pay_hint") + '</div>' +
        '<input type="file" id="receipt-input" accept="image/*" class="hidden" onchange="submitReceipt(' + active.id + ')" />' +
        '<button onclick="document.getElementById(\'receipt-input\').click()" id="receipt-btn" class="press w-full py-3 rounded-xl btn-primary font-semibold text-white text-[13px]">📎 ' + t("ao_pay_upload") + '</button>' +
        '<p id="receipt-error" class="hidden text-red-400 text-[11px] mt-2"></p>' +
      '</div>'
    : "";

  const cancelBtn = (active.status === "awaiting_payment" || active.status === "payment_review")
    ? '<button onclick="cancelActiveOrder(' + active.id + ')" class="press mt-3 w-full py-2.5 rounded-xl pill text-[11px] font-medium text-gray-400">' + t("ao_cancel") + '</button>'
    : "";

  // Заказ из корзины — показываем все товары списком, иначе человек видел бы
  // только один товар из нескольких и не понял бы, за что общая сумма.
  const cartItems = active.cart_items || [];
  const isCart = cartItems.length > 0;
  const titleLine = isCart
    ? '🛒 ' + t("cart_active_title") + ' · ' + cartItems.length + ' ' + t("cart_items_suffix")
    : active.item_name;
  const cartItemsBlock = isCart
    ? '<div class="mt-2 pt-2 border-t border-white/[0.08] space-y-1">' +
        cartItems.map(function(it) {
          return '<div class="flex justify-between gap-2 text-[11px]">' +
            '<span class="text-gray-300 truncate">' + it.item_name + '</span>' +
            '<span class="text-gray-400 flex-shrink-0">' + fmtUZS(it.price_uzs) + '</span>' +
          '</div>';
        }).join("") +
      '</div>'
    : "";

  bar.classList.remove("hidden");
  bar.innerHTML =
    '<div class="glass-card rounded-[20px] p-4 overlay-enter" style="border-color: rgba(42,171,238,0.35);">' +
      // Тап по шапке открывает полноэкранный живой статус заказа — там всё:
      // реквизиты, загрузка чека, "выполняется" и финальная галочка.
      '<div class="flex items-center justify-between gap-2 cursor-pointer" onclick="openOrderFlow({order_id: ' + active.id +
        ', cart_id: ' + (active.cart_id ? "'" + active.cart_id + "'" : "null") + '})">' +
        '<div class="min-w-0">' +
          '<div class="text-[10px] text-neon-blue font-bold uppercase tracking-wider mb-0.5">' + t("ao_title") + (isCart ? "" : " #" + active.id) + '</div>' +
          '<div class="text-[13px] font-semibold text-white truncate">' + titleLine + '</div>' +
          '<div class="text-[11px] text-gray-400 mt-0.5">' + statusText + ' ›</div>' +
        '</div>' +
        '<div class="text-[12px] font-bold text-neon-yellow flex-shrink-0">' + fmtUZS(active.price_uzs) + '</div>' +
      '</div>' +
      cartItemsBlock + payBlock + linkBlock + cancelBtn +
    '</div>';
}

async function cancelActiveOrder(orderId) {
  askConfirm(t("ao_cancel_confirm"), function() { doCancelActiveOrder(orderId); });
}

async function doCancelActiveOrder(orderId) {
  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) return;
  try {
    await fetch(base + "/public/cancel_order", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData, order_id: orderId }),
    });
  } catch (e) { /* молча — просто обновим баннер ниже */ }
  refreshActiveOrder();
}

function copyActiveCard(number) {
  navigator.clipboard.writeText(number);
  if (tg && tg.showAlert) tg.showAlert(t("copied")); else alert(t("copied"));
}

async function submitReceipt(orderId) {
  const input = document.getElementById("receipt-input");
  const btn = document.getElementById("receipt-btn");
  const errorEl = document.getElementById("receipt-error");
  if (!input || !input.files || !input.files[0]) return;

  const file = input.files[0];
  errorEl.classList.add("hidden");
  if (file.size > 25 * 1024 * 1024) {
    errorEl.textContent = t("ao_err_too_big"); errorEl.classList.remove("hidden"); return;
  }

  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) return;

  const prev = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="inline-block w-4 h-4 border-2 border-white/40 border-t-white rounded-full align-middle" style="animation: spin .7s linear infinite;"></span>';

  try {
    const base64 = await receiptToBase64(file);
    const res = await fetch(base + "/public/submit_receipt", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData, order_id: orderId, image_base64: base64 }),
    });
    const data = await res.json();
    if (data.ok) {
      if (tg && tg.showAlert) tg.showAlert(t("ao_receipt_sent")); else alert(t("ao_receipt_sent"));
      refreshActiveOrder();
    } else {
      // Показываем конкретную причину, а не общее "не удалось" —
      // иначе непонятно, что именно исправлять.
      const reasons = {
        wrong_status: t("ao_err_wrong_status"),
        too_big: t("ao_err_too_big"),
        no_image: t("ao_err_no_image"),
        bad_image: t("ao_err_no_image"),
        not_found: t("ao_err_not_found"),
      };
      errorEl.textContent = reasons[data.error] || (t("ao_err_receipt") + " (" + (data.error || res.status) + ")");
      errorEl.classList.remove("hidden");
    }
  } catch (e) {
    errorEl.textContent = t("ao_err_network"); errorEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerHTML = prev;
    input.value = "";
  }
}

function openBotForTutorial() {
  // Открываем чат с ботом, где уже лежит видео-инструкция.
  if (tg && tg.close) tg.close();
}

async function submitRentLink() {
  const input = document.getElementById("rent-link-input");
  const errorEl = document.getElementById("rent-link-error");
  const btn = document.getElementById("rent-link-btn");
  if (!input) return;

  const link = input.value.trim();
  errorEl.classList.add("hidden");
  if (!link) { errorEl.textContent = t("ao_err_empty"); errorEl.classList.remove("hidden"); return; }

  const base = await getShopApiUrl();
  const initData = await waitForInitData();
  if (!base || !initData) return;

  const prev = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="inline-block w-4 h-4 border-2 border-white/40 border-t-white rounded-full align-middle" style="animation: spin .7s linear infinite;"></span>';

  try {
    const res = await fetch(base + "/public/submit_rent_link", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: initData, link: link }),
    });
    const data = await res.json();
    if (data.ok) {
      // Реальный успех от backend, а не таймер. Подарок подключён — показываем
      // это на экране статуса и ждём, пока админ отметит заказ выполненным.
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      showToast(t("ao_connected"));
      if (flowOrder) { pollOrderFlow(); startFlowPolling(); }
      else openOrderFlow({ order_id: data.order_id });
      refreshActiveOrder();
    } else if (data.error === "bad_link") {
      errorEl.textContent = t("ao_err_bad_link"); errorEl.classList.remove("hidden");
    } else {
      errorEl.textContent = t("ao_err_connect"); errorEl.classList.remove("hidden");
    }
  } catch (e) {
    errorEl.textContent = t("ao_err_network"); errorEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerHTML = prev;
  }
}

refreshActiveOrder();
