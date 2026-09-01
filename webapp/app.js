const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.expand(); tg.ready(); }

/* ---------------- i18n ---------------- */
const I18N = {
  uz: {
    ijara_title: "Gift Arendasi", history_title: "Xaridlar tarixi",
    history_empty: "Hozircha xaridlar tarixi bo'sh.", history_hint: "To'liq tarix - botdagi \"Mening buyurtmalarim\" bo'limida.",
    top_title: "Reyting", top_subtitle: "Eng faol mijozlar", top_forming: "Reyting shakllanmoqda", top_hint: "Birinchi xaridni amalga oshiring!",
    referral_title: "Referal tizimi", referral_subtitle: "Do'stlaringizni taklif qiling!", referral_link_label: "Sizning referal havolangiz:", referral_copy: "Havolani nusxalash",
    profile_operator: "Operator", profile_channel: "\ud83d\udce2 Bot kanali", profile_orders_channel: "\ud83d\uded2 Savdo/Orderlar",
    nav_main: "Asosiy", nav_rent: "Ijara", nav_history: "Tarix", nav_referral: "Referal", nav_profile: "Profil",
    modal_to_whom: "Kimga?", modal_to_self: "O'zimga", modal_to_friend: "Do'stimga",
    modal_recipient_label: "Qabul qiluvchi (@username):", modal_message_label: "Xabar (ixtiyoriy):",
    modal_message_placeholder: "Tabrik matni...", modal_rent_days: "Necha kunga?",
    modal_card_label: "To'lov uchun karta (Uzcard/Humo)", modal_card_holder_label: "Qabul qiluvchi",
    modal_copy: "Nusxalash", modal_paid: "To'ladim", modal_cancel: "Bekor qilish",
    err_username: "Username kiriting", err_no_username: "Sizda public username yo'q. Telegram sozlamalaridan o'rnating yoki \"Do'stimga\" tanlang.",
    rent_terms: (fee, refund) => "Xizmat haqi: ~" + fee + ". Ijara tugagach ~" + refund + " qaytariladi.",
    copied: "Nusxalandi!", empty: "Hozircha bo'sh.", rent_days_suffix: "kun", rent_from: "dan", rent_btn: "Ijaraga olish",
    modal_preview: "Telegram-da ko'rish",
    sort_recent: "Yangilari", sort_price_asc: "Narx: arzon", sort_price_desc: "Narx: qimmat", sort_price_min: "Narx: min",
    sort_duration_asc: "Muddat: qisqa", sort_duration_desc: "Muddat: uzun",
    load_more: "Ko'proq ko'rsatish", premium_title: "Telegram Premium olish", premium_subtitle: "O'zingiz yoki yaqiningiz uchun", premium_get_suffix: "olish",
    custom_amount: "Boshqa miqdor", custom_amount_hint: "O'zingiz kiriting", custom_amount_label: "Nechta Stars?",
    recent_recipient_label: "Yaqinda:",
  },
  ru: {
    ijara_title: "Аренда гифтов", history_title: "История покупок",
    history_empty: "Пока пусто.", history_hint: "Полная история - в разделе «Мои заказы» в боте.",
    top_title: "Рейтинг", top_subtitle: "Самые активные клиенты", top_forming: "Рейтинг формируется", top_hint: "Сделайте первую покупку!",
    referral_title: "Реферальная система", referral_subtitle: "Приглашай друзей и получай бонусы!", referral_link_label: "Твоя реферальная ссылка:", referral_copy: "Скопировать ссылку",
    profile_operator: "Оператор", profile_channel: "\ud83d\udce2 Канал бота", profile_orders_channel: "\ud83d\uded2 Заказы/Отзывы",
    nav_main: "Главная", nav_rent: "Аренда", nav_history: "История", nav_referral: "Рефералы", nav_profile: "Профиль",
    modal_to_whom: "Кому?", modal_to_self: "Себе", modal_to_friend: "Другу",
    modal_recipient_label: "Получатель (@username):", modal_message_label: "Сообщение (необязательно):",
    modal_message_placeholder: "Текст поздравления...", modal_rent_days: "На сколько дней?",
    modal_card_label: "Карта для оплаты (Uzcard/Humo)", modal_card_holder_label: "Получатель",
    modal_copy: "Скопировать", modal_paid: "Я оплатил", modal_cancel: "Отмена",
    err_username: "Введите username", err_no_username: "У вас нет публичного username. Установите в настройках Telegram или выберите \"Другу\".",
    rent_terms: (fee, refund) => "Сервисный сбор: ~" + fee + ". После окончания аренды вернётся ~" + refund + ".",
    copied: "Скопировано!", empty: "Пока пусто.", rent_days_suffix: "дн.", rent_from: "от", rent_btn: "Арендовать",
    modal_preview: "Смотреть в Telegram",
    sort_recent: "Новинки", sort_price_asc: "Цена: дешевле", sort_price_desc: "Цена: дороже", sort_price_min: "Цена: мин",
    sort_duration_asc: "Срок: короче", sort_duration_desc: "Срок: длиннее",
    load_more: "Показать ещё", premium_title: "Оформить Telegram Premium", premium_subtitle: "Себе или близкому человеку", premium_get_suffix: "оформить",
    custom_amount: "Другое количество", custom_amount_hint: "Введите сами", custom_amount_label: "Сколько звёзд?",
    recent_recipient_label: "Недавнее:",
  },
  en: {
    ijara_title: "Gift rental", history_title: "Purchase history",
    history_empty: "Nothing here yet.", history_hint: "Full history is in \"My orders\" in the bot chat.",
    top_title: "Rating", top_subtitle: "Most active customers", top_forming: "Rating is forming", top_hint: "Make your first purchase!",
    referral_title: "Referral program", referral_subtitle: "Invite friends and get bonuses!", referral_link_label: "Your referral link:", referral_copy: "Copy link",
    profile_operator: "Operator", profile_channel: "\ud83d\udce2 Bot channel", profile_orders_channel: "\ud83d\uded2 Orders channel",
    nav_main: "Home", nav_rent: "Rent", nav_history: "History", nav_referral: "Referral", nav_profile: "Profile",
    modal_to_whom: "For whom?", modal_to_self: "Myself", modal_to_friend: "A friend",
    modal_recipient_label: "Recipient (@username):", modal_message_label: "Message (optional):",
    modal_message_placeholder: "Congratulation text...", modal_rent_days: "For how many days?",
    modal_card_label: "Payment card (Uzcard/Humo)", modal_card_holder_label: "Recipient",
    modal_copy: "Copy", modal_paid: "I've paid", modal_cancel: "Cancel",
    err_username: "Enter a username", err_no_username: "You don't have a public username. Set one in Telegram settings or choose \"A friend\".",
    rent_terms: (fee, refund) => "Service fee: ~" + fee + ". ~" + refund + " is refunded after the rental ends.",
    copied: "Copied!", empty: "Nothing here yet.", rent_days_suffix: "days", rent_from: "from", rent_btn: "Rent",
    modal_preview: "View in Telegram",
    sort_recent: "Newest", sort_price_asc: "Price: cheapest", sort_price_desc: "Price: priciest", sort_price_min: "Price: min",
    sort_duration_asc: "Duration: shortest", sort_duration_desc: "Duration: longest",
    load_more: "Show more", premium_title: "Get Telegram Premium", premium_subtitle: "For yourself or someone else", premium_get_suffix: "get",
    custom_amount: "Custom amount", custom_amount_hint: "Enter your own", custom_amount_label: "How many Stars?",
    recent_recipient_label: "Recent:",
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
  if (currentTab === "ijara") renderIjara();
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

/* ---------------- Загрузка каталога ---------------- */
const catalog = { stars: [], premium: [], simple_gift: [], nft_rent: [] };
let currentCategory = "stars";
let currentTab = "asosiy";
let currentRentSort = "recently_touch";

async function loadCatalog(cat, forceReload) {
  if (catalog[cat].length && !forceReload) return catalog[cat];
  const res = await fetch("/api/" + cat);
  if (!res.ok) throw new Error("bad response " + cat);
  const data = await res.json();
  catalog[cat] = data.map(normalizeItem(cat));
  return catalog[cat];
}

async function fetchRentPage(cursor) {
  const isClientDesc = currentRentSort === "price_desc_client";
  const backendSort = isClientDesc ? "price_per_day" : currentRentSort;
  let url = "/api/nft_rent?sort_by=" + backendSort;
  if (cursor) url += "&cursor=" + encodeURIComponent(cursor);
  const res = await fetch(url);
  if (!res.ok) throw new Error("bad response nft_rent");
  const data = await res.json();
  let mapped = data.items.map(normalizeItem("nft_rent"));
  if (isClientDesc) mapped = mapped.slice().reverse();
  return { items: mapped, nextCursor: data.next_cursor };
}

function normalizeItem(cat) {
  return function(raw) {
    if (cat === "stars") return { kind: "stars", title: raw.amount.toLocaleString("ru-RU") + " Stars", price: raw.price_uzs, emoji: "⭐️", raw: raw };
    if (cat === "premium") return { kind: "premium", title: raw.label, price: raw.price_uzs, emoji: "👑", raw: raw };
    if (cat === "simple_gift") return { kind: "simple_gift", title: raw.star_count + "⭐", price: raw.price_uzs, emoji: raw.sticker_emoji || "🎁", raw: raw };
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

  if (currentCategory === "premium") { await renderPremiumList(); return; }
  document.getElementById("premium-list").classList.add("hidden");
  grid.classList.remove("hidden");

  grid.innerHTML = skeletonHTML(6, "h-24");
  let items;
  try { items = await loadCatalog(currentCategory); }
  catch (e) { grid.innerHTML = '<p class="col-span-3 text-center text-xs text-gray-500 py-8">' + t("empty") + '</p>'; return; }

  if (!items.length) { grid.innerHTML = '<p class="col-span-3 text-center text-xs text-gray-500 py-8">' + t("empty") + '</p>'; return; }

  const customCardHTML = currentCategory === "stars"
    ? '<div id="stars-custom-card" class="bg-white/5 backdrop-blur-md border border-dashed border-white/20 rounded-2xl p-3 flex flex-col items-center text-center cursor-pointer active:scale-95 transition-all hover:bg-white/10">' +
        '<div class="text-3xl my-2">✏️</div>' +
        '<div class="text-[10px] text-gray-300 mt-1 mb-1 leading-tight h-6 overflow-hidden">' + t("custom_amount") + '</div>' +
        '<div class="text-[10px] font-bold text-gray-400">' + t("custom_amount_hint") + '</div>' +
      '</div>'
    : "";

  grid.innerHTML = items.map(function(it, i) {
    return '<div data-i="' + i + '" class="product-card bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-3 flex flex-col items-center text-center cursor-pointer active:scale-95 transition-all hover:bg-white/10 hover:border-white/20 shadow-lg shadow-black/20">' +
      '<div class="text-3xl my-2 animated-gift">' + it.emoji + '</div>' +
      '<div class="text-[10px] text-gray-300 mt-1 mb-1 leading-tight h-6 overflow-hidden">' + it.title + '</div>' +
      '<div class="text-[10px] font-bold text-neon-yellow">' + fmtUZS(it.price) + '</div>' +
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

  return '<div data-i="' + i + '" class="rent-card bg-[#0d1424] border border-white/10 rounded-2xl overflow-hidden flex flex-col cursor-pointer active:scale-[0.98] transition-all hover:border-white/20 shadow-lg shadow-black/20">' +
    '<div class="rent-img relative h-44">' +
      imgBlock +
      discountBadge +
      '<span class="absolute bottom-2 right-2 bg-black/60 backdrop-blur text-[10px] font-semibold px-2 py-1 rounded-lg text-gray-200">' +
        t("rent_from") + ' ' + it.raw.min_duration_days + '-' + it.raw.max_duration_days + ' ' + t("rent_days_suffix") +
      '</span>' +
    '</div>' +
    '<div class="p-3.5 flex flex-col gap-1.5">' +
      '<div class="flex items-center justify-between">' +
        '<div class="text-sm font-bold text-white truncate">' + it.title + '</div>' +
        numberBadge +
      '</div>' +
      '<div class="text-sm font-bold text-neon-yellow">' + fmtUZS(it.price) + ' <span class="text-[11px] text-gray-400 font-normal">· 1 ' + t("rent_days_suffix") + '</span></div>' +
      '<button data-i="' + i + '" class="rent-btn mt-2 w-full py-2.5 rounded-xl bg-gradient-to-r from-neon-blue to-blue-600 font-bold text-white text-sm active:scale-95 transition-all shadow-[0_4px_14px_rgba(59,130,246,0.35)]">' + t("rent_btn") + '</button>' +
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
  btn.className = "col-span-2 mt-1 py-3 rounded-xl bg-white/5 border border-white/10 text-sm font-semibold text-gray-300 active:scale-95 transition-all";
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
    optionsEl.innerHTML = items.map(function(it, i) {
      const selected = i === selectedPremiumIndex;
      return '<div data-i="' + i + '" class="premium-option flex items-center justify-between gap-3 rounded-2xl p-3.5 cursor-pointer transition-all border ' +
        (selected ? "bg-neon-blue/10 border-neon-blue" : "bg-white/5 border-white/10") + '">' +
        '<div class="flex items-center gap-3">' +
          '<span class="w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ' + (selected ? "border-neon-blue" : "border-gray-500") + '">' +
            (selected ? '<span class="w-2.5 h-2.5 rounded-full bg-neon-blue"></span>' : "") +
          '</span>' +
          '<span class="text-xl">👑</span>' +
          '<span class="text-sm font-semibold text-white">' + it.title + '</span>' +
        '</div>' +
        '<span class="text-sm font-bold text-neon-yellow">' + fmtUZS(it.price) + '</span>' +
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
    btn.className = "cat-btn px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs whitespace-nowrap text-gray-300";
  });
  document.getElementById("cat-" + cat).className = "cat-btn px-4 py-1.5 rounded-full bg-gradient-to-r from-neon-yellow to-amber-500 text-black text-xs font-bold whitespace-nowrap shadow-[0_0_10px_rgba(234,179,8,0.3)]";
  renderItems();
}

function switchTab(tab) {
  currentTab = tab;
  ["asosiy","ijara","tarix","top","referal","profil"].forEach(function(x) {
    document.getElementById("view-" + x).classList.add("view-hidden");
  });
  document.getElementById("view-" + tab).classList.remove("view-hidden");
  Array.prototype.forEach.call(document.querySelectorAll(".nav-btn"), function(btn) {
    btn.classList.remove("text-neon-blue"); btn.classList.add("text-gray-500");
  });
  document.getElementById("tab-" + tab).classList.remove("text-gray-500");
  document.getElementById("tab-" + tab).classList.add("text-neon-blue");
  if (tab === "ijara") renderIjara();
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
  if (!activeItem || activeItem.kind !== "nft_rent") return;
  const min = activeItem.raw.min_duration_days, max = activeItem.raw.max_duration_days;
  const next = rentDays + delta;
  if (next < min || next > max) return;
  rentDays = next;
  document.getElementById("days-value").textContent = rentDays;
  document.getElementById("modal-price").textContent = fmtUZS(activeItem.price * rentDays);
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
  rentDays = item.kind === "nft_rent" ? item.raw.min_duration_days : 1;

  document.getElementById("modal-title").textContent = item.title + (item.raw && item.raw.number ? " #" + item.raw.number : "");
  const emojiEl = document.getElementById("modal-emoji");
  if (item.image) {
    emojiEl.innerHTML = '<img src="' + item.image + '" class="w-10 h-10 rounded-lg object-cover" onerror="this.parentElement.textContent=\'' + item.emoji + '\';" />';
  } else {
    emojiEl.textContent = item.emoji;
  }
  document.getElementById("modal-price").textContent = fmtUZS(item.kind === "nft_rent" ? item.price * rentDays : item.price);
  document.getElementById("gift-message").value = "";
  document.getElementById("gift-username").value = "";
  document.getElementById("modal-error").classList.add("hidden");
  setRecipient("self");

  document.getElementById("rent-days-field").classList.toggle("hidden", item.kind !== "nft_rent");
  if (item.kind === "nft_rent") document.getElementById("days-value").textContent = rentDays;

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

function copyReferral() {
  const link = document.getElementById("referral-link").textContent;
  navigator.clipboard.writeText(link);
  if (tg && tg.showAlert) tg.showAlert(t("copied")); else alert(t("copied"));
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
function sendPaymentInfo() {
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
    payload.item_name = "Подарок " + item.emoji + " (" + item.raw.star_count + "⭐)"; payload.price = item.raw.price_uzs; payload.quantity = 1; payload.gift_id = item.raw.id;
  } else if (item.kind === "nft_rent") {
    payload.item_name = item.raw.name; payload.nft_address = item.raw.nft_address;
    payload.base_price_per_day_gram = item.raw.base_price_per_day_gram;
    payload.min_days = item.raw.min_duration_days; payload.max_days = item.raw.max_duration_days;
    payload.days = rentDays;
  }

  if (recipientType === "friend" && friendUsername) saveRecentRecipient(friendUsername);

  if (tg && tg.sendData) {
    tg.sendData(JSON.stringify(payload));
    tg.close();
  } else {
    alert("DEMO (Telegram ichida ochish kerak): " + JSON.stringify(payload, null, 2));
  }
}

/* ---------------- Профиль / рефералка / условия аренды ---------------- */
function initProfile() {
  const u = tg && tg.initDataUnsafe ? tg.initDataUnsafe.user : null;
  if (!u) return;
  document.getElementById("profile-name").textContent = u.first_name || "Mijoz";
  document.getElementById("profile-username").textContent = u.username ? "@" + u.username : "";
  document.getElementById("profile-id").textContent = "ID: " + u.id;
  document.getElementById("profile-avatar").textContent = (u.first_name ? u.first_name.charAt(0) : "?").toUpperCase();
}

async function initReferral() {
  try {
    const u = tg && tg.initDataUnsafe ? tg.initDataUnsafe.user : null;
    const res = await fetch("/api/bot_info");
    const data = await res.json();
    const ref = u ? "https://t.me/" + data.username + "?start=ref" + u.id : "https://t.me/" + data.username;
    document.getElementById("referral-link").textContent = ref;
  } catch (e) { /* тихо игнорируем */ }
}

async function renderRentTerms() {
  try {
    const res = await fetch("/api/rent_terms");
    const d = await res.json();
    document.getElementById("rent-terms-text").textContent = t("rent_terms")(fmtUZS(d.fee_uzs), fmtUZS(d.refund_uzs));
  } catch (e) { /* тихо игнорируем */ }
}

/* ---------------- Init ---------------- */
applyI18n();
initProfile();
initReferral();
initSupportInfo();
