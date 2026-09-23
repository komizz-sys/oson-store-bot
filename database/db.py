import os
import random

import aiosqlite
import config

CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    category TEXT NOT NULL,          -- stars | premium | nft_rent | simple_gift
    item_name TEXT NOT NULL,         -- напр. "100 звёзд", "Premium 3 мес", "Plush Pepe"
    quantity INTEGER DEFAULT 1,
    price_uzs INTEGER NOT NULL,
    recipient TEXT,                  -- @username или ссылка, куда доставить звёзды/подарок
    recipient_user_id INTEGER,       -- числовой user_id получателя, если известен точно
                                      -- (заполняется, когда заказ оформлен "себе" — тогда
                                      -- повторный поиск по @username при выполнении не нужен)
    rent_days INTEGER,               -- только для аренды NFT
    nft_address TEXT,                -- адрес NFT на MarketApp (для аренды)
    base_price_per_day_gram TEXT,    -- базовая цена/день в GRAM (для аренды)
    status TEXT DEFAULT 'awaiting_payment',
    -- awaiting_payment -> payment_review -> paid -> fulfilling -> completed / rejected
    payment_proof_file_id TEXT,
    receipt_fingerprint TEXT,        -- отпечаток чека: один и тот же файл = одна оплата
                                      -- (для фото из чата — file_unique_id, для витрины — хэш картинки)
    admin_comment TEXT,
    content_video_url TEXT,          -- видео-инструкция после выполнения
    content_text TEXT,               -- текст-инструкция после выполнения
    rent_link TEXT,                  -- ссылка от клиента для подключения арендованного гифта
    expected_amount_uzs INTEGER,     -- уникальная сумма к оплате (price_uzs + анти-коллизийная надбавка)
    cart_id TEXT,                    -- если заказ оформлен из корзины: общий id всех товаров этой корзины
                                      -- (оплата у них одна на всех, expected_amount_uzs = сумма всей корзины)
    is_extension INTEGER DEFAULT 0,  -- 1 = это ПРОДЛЕНИЕ уже действующей аренды, а не новая аренда
    parent_order_id INTEGER,         -- какой заказ аренды продлеваем (для is_extension = 1)
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_SUPPORT_TABLE = """
CREATE TABLE IF NOT EXISTS support_messages (
    admin_id INTEGER NOT NULL,
    admin_message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (admin_id, admin_message_id)
);
"""

# Журнал автоплатежей с TON-кошелька магазина. Здесь настоящие деньги, поэтому:
#
# 1) UNIQUE(order_id, purpose) — главная защита от ДВОЙНОЙ оплаты. Повторить
#    попытку может кто угодно: перезапуск бота на Railway, повторное нажатие
#    кнопки админом, автоповтор после таймаута сети. Строка вставляется ДО
#    отправки транзакции — если такая уже есть, вторая оплата просто не
#    начнётся. Потерять 0.29 TON на дубле обиднее, чем разбираться с зависшей
#    строкой в статусе 'sending'.
# 2) Журнал нужен и для суточного лимита: сколько уже потрачено за сегодня.
CREATE_TON_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS ton_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    purpose TEXT NOT NULL,           -- rent | stars | premium
    amount_nano INTEGER NOT NULL,    -- сколько списываем, в нанотонах
    destination TEXT,
    status TEXT DEFAULT 'sending',   -- sending -> sent / failed
    error TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (order_id, purpose)
);
"""

# Кого не показывать в публичном рейтинге (вкладка TOP в витрине).
# Нужно для своих тестовых аккаунтов и для случаев, когда заказ был реальным,
# но светить клиента в топе не хочется. Сам заказ при этом остаётся в базе и в
# статистике — скрывается только строка в рейтинге.
# Карточки чеков, отправленные админу. Нужны, чтобы бот мог САМ дописать в уже
# отправленное сообщение «оплачено автоматически» и «ВЫПОЛНЕНО»: иначе админ
# видит в чате только старую карточку с кнопками и не понимает, закрыт заказ
# или нет — ровно та путаница, из-за которой заказы подтверждались дважды.
#
# Храним и исходную подпись: отредактировать сообщение можно только целиком,
# а прочитать его текст у Telegram нельзя.
CREATE_ADMIN_CARDS_TABLE = """
CREATE TABLE IF NOT EXISTS admin_cards (
    order_id   INTEGER NOT NULL,
    chat_id    INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    caption    TEXT    NOT NULL DEFAULT '',
    notes      TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (order_id, chat_id)
)
"""

# Ожидаемые доплаты: заказ #N недоплачен на X сум. Сумма — ключ: именно по ней
# бот узнаёт отдельный маленький перевод и понимает, к какому заказу его
# приложить. Без этой таблицы доплата пришла бы в никуда.
CREATE_PENDING_TOPUPS_TABLE = """
CREATE TABLE IF NOT EXISTS pending_topups (
    amount     INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Баланс клиента — внутренний счёт магазина.
#
# Зачем он появился: банк почти всегда удерживает комиссию, и на карту
# приходит не та сумма, которую человек отправил (отправил 50 000 — пришло
# 49 559). Для заказа это провал: сумма не совпала, заказ висит. Для баланса —
# просто зачисление на столько, сколько реально дошло. Дальше заказы
# оплачиваются с баланса мгновенно и ровно, без чеков и без сверок.
#
# Деньги на балансе НЕ выводятся обратно — это счёт для покупок внутри
# магазина, и клиенту это сказано прямым текстом при пополнении.
CREATE_BALANCE_TXNS_TABLE = """
CREATE TABLE IF NOT EXISTS balance_txns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    delta_uzs  INTEGER NOT NULL,
    reason     TEXT,
    order_id   INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# Заявка на пополнение: клиент сказал «хочу пополнить на N», бот выдал ему
# сумму с уникальным хвостом. По ней и опознаём поступление — SMS от банка
# сообщает сумму, но не отправителя, и другого способа понять, чей это
# перевод, у нас нет.
CREATE_TOPUP_REQUESTS_TABLE = """
CREATE TABLE IF NOT EXISTS topup_requests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    expected_uzs INTEGER NOT NULL,
    status     TEXT DEFAULT 'pending',
    receipt_fp TEXT,
    credited_uzs INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_BANNED_TABLE = """
CREATE TABLE IF NOT EXISTS banned_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    reason TEXT,
    banned_by INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_LEADERBOARD_HIDDEN_TABLE = """
CREATE TABLE IF NOT EXISTS leaderboard_hidden (
    user_id INTEGER PRIMARY KEY,
    reason TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


async def init_db():
    # Папка под базу может не существовать — например, при первом запуске на
    # свежесмонтированном Volume (/data) или если её нет в репозитории
    # (git не хранит пустые папки). Без этого sqlite падает с
    # "unable to open database file" и бот вообще не стартует.
    db_dir = os.path.dirname(config.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(CREATE_USERS_TABLE)
        await db.execute(CREATE_ORDERS_TABLE)
        await db.execute(CREATE_SUPPORT_TABLE)
        await db.execute(CREATE_TON_PAYMENTS_TABLE)
        await db.execute(CREATE_LEADERBOARD_HIDDEN_TABLE)
        await db.execute(CREATE_BANNED_TABLE)
        await db.execute(CREATE_ADMIN_CARDS_TABLE)
        await db.execute(CREATE_BALANCE_TXNS_TABLE)
        await db.execute(CREATE_TOPUP_REQUESTS_TABLE)
        await db.execute(CREATE_PENDING_TOPUPS_TABLE)
        # Миграции для баз, созданных до появления этих полей/таблиц
        for stmt in (
            "ALTER TABLE users ADD COLUMN language TEXT",
            "ALTER TABLE users ADD COLUMN balance_uzs INTEGER NOT NULL DEFAULT 0",
            "CREATE INDEX IF NOT EXISTS idx_topups_amount ON topup_requests(expected_uzs)",
            "ALTER TABLE topup_requests ADD COLUMN receipt_fp TEXT",
            "ALTER TABLE users ADD COLUMN last_seen TEXT",
            "ALTER TABLE orders ADD COLUMN content_video_url TEXT",
            "ALTER TABLE orders ADD COLUMN content_text TEXT",
            "ALTER TABLE orders ADD COLUMN recipient_user_id INTEGER",
            "ALTER TABLE orders ADD COLUMN rent_link TEXT",
            "ALTER TABLE orders ADD COLUMN reminder_sent INTEGER DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN expected_amount_uzs INTEGER",
            "ALTER TABLE orders ADD COLUMN cart_id TEXT",
            "ALTER TABLE orders ADD COLUMN is_extension INTEGER DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN parent_order_id INTEGER",
            "ALTER TABLE orders ADD COLUMN receipt_fingerprint TEXT",
            # Ссылка вида https://t.me/nft/swisswatch-12345 — «паспорт» именно
            # этого экземпляра подарка. Нужна, чтобы после подключения дать
            # клиенту кнопку прямо на его подарок: Telegram показывает
            # арендованный гифт в профиле только когда владелец сам включит
            # показ, а найти гифт без ссылки человек не может.
            "ALTER TABLE orders ADD COLUMN nft_preview_url TEXT",
            "CREATE INDEX IF NOT EXISTS idx_orders_receipt ON orders(receipt_fingerprint)",
        ):
            try:
                await db.execute(stmt)
            except Exception:
                pass  # уже есть
        await db.commit()


async def upsert_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, username, full_name, last_seen) VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name,
               last_seen=datetime('now')""",
            (user_id, username, full_name),
        )
        await db.commit()


async def get_stats() -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-1 day')"
        ) as cur:
            active_24h = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-7 day')"
        ) as cur:
            active_7d = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total_orders = (await cur.fetchone())[0]
        async with db.execute("SELECT status, COUNT(*) FROM orders GROUP BY status") as cur:
            by_status = {row[0]: row[1] async for row in cur}
    return {
        "total_users": total_users,
        "active_24h": active_24h,
        "active_7d": active_7d,
        "total_orders": total_orders,
        "orders_by_status": by_status,
    }


# Статусы, которые считаем "деньги реально получены" — оплата подтверждена
# админом (payment_review ещё не считаем, там оплата не проверена).
PAID_STATUSES = ("paid", "fulfilling", "completed")


async def get_revenue_stats(since_sql: str | None, ton_gram_rate_uzs: int) -> dict:
    """
    Доход и РАСХОД по категориям за период (или за всё время, если since_sql=None).

    Откуда берётся расход — два источника, в порядке надёжности:

    1) ЖУРНАЛ АВТОПЛАТЕЖЕЙ (ton_payments) — сколько TON реально ушло с
       кошелька за конкретный заказ. Это не оценка, а факт: ровно та сумма,
       которую подписал и отправил бот. Работает для заказов, оплаченных
       автоматически (звёзды, аренда).

    2) РАСЧЁТ ПО ЦЕНЕ АРЕНДЫ — base_price_per_day_gram * rent_days. Нужен
       для заказов ДО включения автооплаты, когда админ платил вручную из
       кошелька и в журнале записи нет.

    Оба переводятся в сумы по ТЕКУЩЕМУ курсу TON: курс на момент сделки не
    хранится, поэтому при сильном движении курса старые заказы посчитаются
    чуть иначе. Для текущей недели/месяца разница незаметна.

    Звёзды и премиум, купленные вручную (без автооплаты), в расход не
    попадают — бот не может знать, сколько за них заплатили. Такие суммы
    по-прежнему вносятся руками, и в ответе видно, сколько заказов
    осталось непосчитанными.

    -> {
        "income_by_category": {...}, "income_total": int, "orders_count": int,
        "rent_auto_cost_uzs": int,              # как раньше, для совместимости
        "auto_cost_by_category": {...},         # факт из журнала + расчёт аренды
        "auto_cost_total": int,
        "ton_spent_gram": float,                # сколько TON списано за период
        "orders_without_cost": int,             # заказы, по которым расход неизвестен
    }
    """
    status_placeholders = ",".join("?" for _ in PAID_STATUSES)
    where = f"status IN ({status_placeholders})"
    params: list = list(PAID_STATUSES)
    if since_sql:
        where += " AND created_at >= ?"
        params.append(since_sql)

    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            f"SELECT category, COALESCE(SUM(price_uzs), 0), COUNT(*) FROM orders WHERE {where} GROUP BY category",
            params,
        ) as cur:
            rows = await cur.fetchall()

        # Аренда, оплаченная ВРУЧНУЮ (в журнале автоплатежей записи нет) —
        # считаем по цене лота. Заказы с автооплатой исключаем, иначе
        # расход по ним посчитается дважды.
        async with db.execute(
            f"""SELECT COALESCE(SUM(CAST(o.base_price_per_day_gram AS REAL) * o.rent_days), 0)
                FROM orders o WHERE {where.replace('status', 'o.status').replace('created_at', 'o.created_at')}
                AND o.category = 'nft_rent'
                AND o.base_price_per_day_gram IS NOT NULL AND o.rent_days IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM ton_payments p
                                WHERE p.order_id = o.id AND p.status = 'sent')""",
            params,
        ) as cur:
            rent_gram_manual = (await cur.fetchone())[0] or 0

        # Аренда с автооплатой — берём ФАКТ: сколько нанотонов реально ушло.
        # Только аренда: у звёзд и премиума расход считается по закупочной
        # цене (ниже), и брать их ещё и отсюда значило бы посчитать дважды.
        async with db.execute(
            f"""SELECT COALESCE(SUM(p.amount_nano), 0)
                FROM ton_payments p JOIN orders o ON o.id = p.order_id
                WHERE p.status = 'sent' AND o.category = 'nft_rent'
                  AND {where.replace('status', 'o.status').replace('created_at', 'o.created_at')}""",
            params,
        ) as cur:
            rent_nano_paid = (await cur.fetchone())[0] or 0

        # Звёзды: сколько всего звёзд продано (quantity хранит их количество)
        async with db.execute(
            f"SELECT COALESCE(SUM(quantity), 0) FROM orders WHERE {where} AND category = 'stars'",
            params,
        ) as cur:
            stars_sold = (await cur.fetchone())[0] or 0

        # Премиум: закупка у каждого тарифа своя, поэтому считаем по названиям
        async with db.execute(
            f"SELECT item_name, COUNT(*) FROM orders WHERE {where} AND category = 'premium' GROUP BY item_name",
            params,
        ) as cur:
            premium_rows = await cur.fetchall()

        # Подарки: наценка фиксированная, остальное в цене — расход
        async with db.execute(
            f"""SELECT COALESCE(SUM(price_uzs), 0), COALESCE(SUM(quantity), 0)
                FROM orders WHERE {where} AND category = 'simple_gift'""",
            params,
        ) as cur:
            gift_price_total, gift_qty = await cur.fetchone()

    income_by_category = {row[0]: row[1] for row in rows}
    orders_count = sum(row[2] for row in rows)
    income_total = sum(income_by_category.values())

    NANO = 1_000_000_000
    auto_cost_by_category: dict[str, int] = {}

    # --- Аренда: факт по кошельку + расчёт для оплаченных вручную ---
    rent_gram_total = (rent_nano_paid / NANO) + rent_gram_manual
    if rent_gram_total:
        auto_cost_by_category["nft_rent"] = round(rent_gram_total * ton_gram_rate_uzs)

    # --- Звёзды: количество × закупочная цена звезды ---
    if stars_sold:
        auto_cost_by_category["stars"] = round(stars_sold * config.STARS_COST_UZS)

    # --- Премиум: у каждого тарифа своя закупка (data/prices.json, cost_uzs) ---
    premium_cost, premium_unknown = _premium_cost(premium_rows)
    if premium_cost:
        auto_cost_by_category["premium"] = premium_cost

    # --- Подарки: цена минус наша наценка ---
    if gift_price_total:
        cost = gift_price_total - config.SIMPLE_GIFT_MARKUP_UZS * (gift_qty or 0)
        auto_cost_by_category["simple_gift"] = max(0, round(cost))

    return {
        "income_by_category": income_by_category,
        "income_total": income_total,
        "orders_count": orders_count,
        # Старое поле оставлено как было — аналитика на него уже опирается
        "rent_auto_cost_uzs": auto_cost_by_category.get("nft_rent", 0),
        "auto_cost_by_category": auto_cost_by_category,
        "auto_cost_total": sum(auto_cost_by_category.values()),
        "ton_spent_gram": round(rent_gram_total, 4),
        "stars_sold": stars_sold,
        # Тарифы премиума, для которых закупка не указана в прайсе — их расход
        # не посчитан, и об этом нужно честно сказать в отчёте
        "premium_unknown": premium_unknown,
    }


def _premium_cost(premium_rows) -> tuple[int, list[str]]:
    """
    Расход по Premium: у каждого тарифа своя закупочная цена, она лежит
    в data/prices.json рядом с ценой продажи (поле cost_uzs).

    Сопоставляем по названию тарифа. Заказ хранит item_name вида
    "Premium — 3 месяца", а в прайсе лежит просто "3 месяца", поэтому
    ищем вхождение. Тарифы, для которых закупка не указана, возвращаем
    отдельным списком — чтобы отчёт не делал вид, что посчитал всё.
    -> (сумма расхода, [названия непосчитанных тарифов])
    """
    try:
        from services.prices import get_premium_packages
        packages = get_premium_packages()
    except Exception:
        return 0, []

    total = 0
    unknown: list[str] = []
    for item_name, count in premium_rows:
        name = item_name or ""
        match = next((p for p in packages if p.get("label") and p["label"] in name), None)
        cost = (match or {}).get("cost_uzs")
        if cost:
            total += int(cost) * count
        else:
            unknown.append(name)
    return total, unknown


async def save_support_mapping(admin_id: int, admin_message_id: int, user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO support_messages (admin_id, admin_message_id, user_id) VALUES (?, ?, ?)",
            (admin_id, admin_message_id, user_id),
        )
        await db.commit()


async def get_support_user(admin_id: int, admin_message_id: int) -> int | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM support_messages WHERE admin_id=? AND admin_message_id=?",
            (admin_id, admin_message_id),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def get_user_language(user_id: int) -> str | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT language FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_user_language(user_id: int, language: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE users SET language=? WHERE user_id=?", (language, user_id))
        await db.commit()


async def create_order(**kwargs) -> int:
    fields = ", ".join(kwargs.keys())
    placeholders = ", ".join("?" for _ in kwargs)
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            f"INSERT INTO orders ({fields}) VALUES ({placeholders})",
            tuple(kwargs.values()),
        )
        await db.commit()
        return cursor.lastrowid


async def set_order_status(order_id: int, status: str, admin_comment: str | None = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        if admin_comment is not None:
            await db.execute(
                "UPDATE orders SET status=?, admin_comment=? WHERE id=?",
                (status, admin_comment, order_id),
            )
        else:
            await db.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        await db.commit()


async def attach_payment_proof(order_id: int, file_id: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET payment_proof_file_id=?, status='payment_review' WHERE id=?",
            (file_id, order_id),
        )
        await db.commit()


# Заказы в этих статусах ещё "живые" — их expected_amount_uzs занят и не может
# быть выдан другому заказу, пока этот не оплатят или не отменят/просрочат.
UNPAID_STATUSES = ("awaiting_payment", "payment_review")

# Не выдавать сумму дороже (базовая цена + это число) — чтобы разница не
# бросалась в глаза клиенту и не выглядела как "странная" сумма.
DEFAULT_MAX_AMOUNT_OFFSET = 500

# Считаем заказ просроченным (и освобождаем его уникальную сумму), если он
# висит неоплаченным дольше этого времени.
UNIQUE_AMOUNT_ORDER_TTL_MINUTES = int(
    getattr(config, "ORDER_PAYMENT_TTL_MINUTES", 0) or 30
)


async def allocate_unique_amount(base_price_uzs: int, max_offset: int = DEFAULT_MAX_AMOUNT_OFFSET) -> int:
    """
    УСТАРЕЛО: оставлено для совместимости. Выдаёт сумму, но НЕ закрепляет её
    за заказом, из-за чего два одновременных заказа могли получить одну и ту
    же сумму. Используй allocate_and_set_expected_amount().
    """
    return await _pick_free_amount(base_price_uzs, max_offset)


async def _pick_free_amount(base_price_uzs: int, max_offset: int, db=None) -> int:
    """
    Свободная сумма = цена + надбавка 1..max_offset, которую сейчас никто не ждёт.

    Занятыми считаем не только активные заказы, но и отменённые за последние
    сутки. Иначе выходит так: заказ протух, его сумму отдали новому клиенту,
    а деньги по старой сумме приходят через час — и подтверждается ЧУЖОЙ заказ.
    """
    # Суммы заказов И суммы незакрытых пополнений — один общий пул. Если их
    # не объединить, заказу и пополнению может достаться одна сумма, и по
    # поступлению будет непонятно, что это: оплата товара или пополнение счёта.
    query = (
        "SELECT expected_amount_uzs FROM orders WHERE expected_amount_uzs IS NOT NULL AND ("
        f"  status IN ({','.join('?' for _ in UNPAID_STATUSES)})"
        "  OR (status = 'rejected' AND created_at >= datetime('now', '-1 day'))"
        ")"
    )
    topup_query = (
        "SELECT expected_uzs FROM topup_requests "
        "WHERE status = 'pending' AND created_at >= datetime('now', '-1 day')"
    )

    async def _collect(conn):
        async with conn.execute(query, UNPAID_STATUSES) as cur:
            found = {row[0] async for row in cur}
        try:
            async with conn.execute(topup_query) as cur:
                found |= {row[0] async for row in cur}
        except Exception:
            pass  # таблицы ещё нет (первый запуск после обновления)
        return found

    if db is None:
        async with aiosqlite.connect(config.DB_PATH) as conn:
            taken = await _collect(conn)
    else:
        taken = await _collect(db)

    candidates = [
        base_price_uzs + offset
        for offset in range(1, max_offset + 1)
        if (base_price_uzs + offset) not in taken
    ]
    if not candidates:
        # Свободных надбавок не осталось — не роняем оформление заказа,
        # но и базовую цену не выдаём: по ней платёж не опознать.
        # Берём надбавку за пределами обычного диапазона.
        return base_price_uzs + max_offset + random.randint(1, 50)
    return random.choice(candidates)


async def allocate_and_set_expected_amount(order_ids, base_price_uzs: int,
                                           max_offset: int = DEFAULT_MAX_AMOUNT_OFFSET) -> int:
    """
    Выдать уникальную сумму и СРАЗУ закрепить её за заказом — одной транзакцией.

    Почему не двумя вызовами, как было раньше: между «посмотрел, какие суммы
    заняты» и «записал свою» успевал влезть второй заказ и взять ту же самую.
    Два клиента получали одинаковую сумму к оплате, и платёж одного
    подтверждал заказ другого. При наплыве после рекламы это перестаёт быть
    теорией. BEGIN IMMEDIATE не даёт двум таким выдачам идти одновременно.

    order_ids — один id или список (вся корзина платит одной суммой).
    """
    ids = [order_ids] if isinstance(order_ids, int) else list(order_ids)
    if not ids:
        return base_price_uzs

    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            amount = await _pick_free_amount(base_price_uzs, max_offset, db)
            placeholders = ",".join("?" for _ in ids)
            await db.execute(
                f"UPDATE orders SET expected_amount_uzs = ? WHERE id IN ({placeholders})",
                (amount, *ids),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return amount


async def set_expected_amount(order_id: int, amount: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE orders SET expected_amount_uzs=? WHERE id=?", (amount, order_id))
        await db.commit()


async def get_order_by_expected_amount(amount: int) -> dict | None:
    """Ищет неоплаченный заказ с такой уникальной суммой — используется, когда
    пришла SMS о поступлении денег на карту, чтобы понять, чей это платёж."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        status_placeholders = ",".join("?" for _ in UNPAID_STATUSES)
        async with db.execute(
            f"SELECT * FROM orders WHERE status IN ({status_placeholders}) AND expected_amount_uzs=? "
            "ORDER BY id DESC LIMIT 1",
            (*UNPAID_STATUSES, amount),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# Пометка в admin_comment у заказа, отменённого автоматически по таймауту.
# Машиночитаемая (а не русская фраза), потому что витрина показывает
# admin_comment клиенту как есть — и узбек увидел бы русский текст.
TIMEOUT_COMMENT = "timeout"

# Сколько часов после автоотмены мы ещё готовы принять чек: человек мог пойти
# к терминалу или ждать, пока банк проведёт перевод. Деньги уже ушли, и
# оставить его без товара — худшее, что может сделать магазин.
LATE_RECEIPT_HOURS = 24


async def find_recent_timeout_order(user_id: int, hours: int = LATE_RECEIPT_HOURS) -> dict | None:
    """
    Последний заказ клиента, отменённый ИМЕННО по таймауту и совсем недавно.

    Нужен, чтобы поздний чек не упирался в стену: клиент присылает скриншот
    уже после автоотмены, бот находит этот заказ и возвращает его в работу.
    Отменённые вручную (админом или самим клиентом) сюда НЕ попадают — там
    отмена осознанная, и воскрешать её по чеку нельзя.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT * FROM orders
                WHERE user_id = ? AND status = 'rejected'
                  AND admin_comment = ?
                  AND created_at >= datetime('now', '-{int(hours)} hours')
                ORDER BY id DESC LIMIT 1""",
            (user_id, TIMEOUT_COMMENT),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def expire_stale_unpaid_orders(ttl_minutes: int = UNIQUE_AMOUNT_ORDER_TTL_MINUTES) -> list[dict]:
    """
    Помечает старые неоплаченные заказы как rejected (истёк срок), освобождая их
    уникальную сумму для новых заказов. Нужно, чтобы клиент, который передумал
    платить, не "занимал" сумму навечно, и не путал ситуацию, если пришлёт
    оплату по старой (уже переиспользованной) сумме через день.
    -> список заказов, которые были просрочены (чтобы уведомить клиентов).
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE status = 'awaiting_payment' "
            f"AND created_at <= datetime('now', '-{int(ttl_minutes)} minutes')"
        ) as cur:
            stale = [dict(r) for r in await cur.fetchall()]

        if stale:
            ids = [o["id"] for o in stale]
            placeholders = ",".join("?" for _ in ids)
            await db.execute(
                f"UPDATE orders SET status='rejected', admin_comment='{TIMEOUT_COMMENT}' "
                f"WHERE id IN ({placeholders})",
                ids,
            )
            await db.commit()
    return stale


async def get_pending_rent_link_order(user_id: int) -> dict | None:
    """
    Самый свежий заказ аренды этого клиента, который уже оплачен, но для
    которого он ещё не прислал ссылку для подключения гифта. Используется,
    чтобы понять, что вот это текстовое сообщение с ссылкой — не случайный
    текст, а именно ответ на видео-инструкцию по конкретному заказу.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM orders
               WHERE user_id = ? AND category = 'nft_rent' AND status = 'paid'
                 AND (rent_link IS NULL OR rent_link = '')
               ORDER BY id DESC LIMIT 1""",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_rent_link(order_id: int, link: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE orders SET rent_link=? WHERE id=?", (link, order_id))
        await db.commit()


async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_orders(user_id: int) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            return [row[0] async for row in cur]


async def get_user_spend_stats(user_id: int) -> dict:
    """
    Личная статистика трат конкретного пользователя (для вкладки "Profil"):
    сколько потратил по каждой категории + всего + его место в общем рейтинге
    по сумме трат (по PAID_STATUSES, за всё время).
    """
    status_placeholders = ",".join("?" for _ in PAID_STATUSES)
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            f"""SELECT category, COALESCE(SUM(price_uzs), 0)
                FROM orders WHERE user_id = ? AND status IN ({status_placeholders})
                GROUP BY category""",
            [user_id, *PAID_STATUSES],
        ) as cur:
            by_category = {row[0]: row[1] async for row in cur}

        async with db.execute(
            f"""SELECT user_id, SUM(price_uzs) AS total FROM orders
                WHERE status IN ({status_placeholders})
                GROUP BY user_id ORDER BY total DESC""",
            list(PAID_STATUSES),
        ) as cur:
            leaderboard = await cur.fetchall()

    total = sum(by_category.values())
    rank = None
    for i, row in enumerate(leaderboard, start=1):
        if row[0] == user_id:
            rank = i
            break

    return {
        "by_category": by_category,
        "total_uzs": total,
        "rank": rank,
        "total_users_ranked": len(leaderboard),
    }


def _leaderboard_where(since_sql: str | None) -> tuple[str, list]:
    """Одно условие на топ и на «моё место» — чтобы цифры не разъезжались."""
    where = f"o.status IN ({','.join('?' for _ in PAID_STATUSES)})"
    params: list = list(PAID_STATUSES)
    if since_sql:
        where += " AND o.created_at >= ?"
        params.append(since_sql)
    # Скрытые вручную аккаунты (см. /hidetop) в публичный рейтинг не попадают
    where += " AND o.user_id NOT IN (SELECT user_id FROM leaderboard_hidden)"
    return where, params


async def get_leaderboard(since_sql: str | None, limit: int = 20) -> list[dict]:
    """
    Топ клиентов по сумме трат (для вкладки "TOP"). since_sql=None — за всё время.
    -> [{"user_id", "username", "full_name", "total_uzs", "orders_count",
         "stars", "gifts", "premium", "rents"}]
    stars — сколько звёзд куплено (у заказа звёзд quantity = число звёзд),
    gifts — сколько подарков, premium/rents — сколько таких заказов.
    """
    where, params = _leaderboard_where(since_sql)
    params.append(limit)
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT o.user_id, u.username, u.full_name,
                       SUM(o.price_uzs) AS total_uzs, COUNT(*) AS orders_count,
                       SUM(CASE WHEN o.category = 'stars' THEN COALESCE(o.quantity, 0) ELSE 0 END) AS stars,
                       SUM(CASE WHEN o.category = 'simple_gift' THEN COALESCE(o.quantity, 1) ELSE 0 END) AS gifts,
                       SUM(CASE WHEN o.category = 'premium' THEN 1 ELSE 0 END) AS premium,
                       SUM(CASE WHEN o.category = 'nft_rent' THEN 1 ELSE 0 END) AS rents
                FROM orders o
                LEFT JOIN users u ON u.user_id = o.user_id
                WHERE {where}
                GROUP BY o.user_id
                ORDER BY total_uzs DESC, MIN(o.id) ASC
                LIMIT ?""",
            params,
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_leaderboard_position(since_sql: str | None, user_id: int | None) -> dict:
    """
    Сколько всего людей в рейтинге за период и где в нём этот клиент.
    -> {"total_people": int, "rank": int|None, "total_uzs": int,
        "next_total_uzs": int|None}  — next_total_uzs у того, кто на место выше.
    Порядок тот же, что в get_leaderboard, иначе «ваше место» не совпадёт
    с тем, что человек видит в списке.
    """
    where, params = _leaderboard_where(since_sql)
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            f"""SELECT o.user_id, SUM(o.price_uzs) AS total
                FROM orders o
                WHERE {where}
                GROUP BY o.user_id
                ORDER BY total DESC, MIN(o.id) ASC""",
            params,
        ) as cur:
            rows = await cur.fetchall()

    out = {"total_people": len(rows), "rank": None, "total_uzs": 0, "next_total_uzs": None}
    if user_id is None:
        return out
    for i, (uid, total) in enumerate(rows):
        if uid == user_id:
            out["rank"] = i + 1
            out["total_uzs"] = int(total or 0)
            if i > 0:
                out["next_total_uzs"] = int(rows[i - 1][1] or 0)
            break
    return out


# ---- Корзина: несколько товаров, одна оплата ----
# Каждый товар корзины — обычная строка в orders (чтобы выполнение, статистика
# и история работали ровно как раньше), но у всех товаров одной корзины общий
# cart_id и ОДИНАКОВАЯ expected_amount_uzs — сумма всей корзины. Так по одной
# SMS о поступлении понятно, что оплачена именно эта корзина целиком.

async def get_cart_orders(cart_id: str) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE cart_id = ? ORDER BY id", (cart_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def set_cart_status(cart_id: str, status: str, admin_comment: str | None = None) -> list[int]:
    """Меняет статус СРАЗУ ВСЕМ товарам корзины — они оплачиваются одной суммой,
    поэтому и подтверждаются/отклоняются только вместе."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        if admin_comment is not None:
            await db.execute(
                "UPDATE orders SET status=?, admin_comment=? WHERE cart_id=?",
                (status, admin_comment, cart_id),
            )
        else:
            await db.execute("UPDATE orders SET status=? WHERE cart_id=?", (status, cart_id))
        await db.commit()
        async with db.execute("SELECT id FROM orders WHERE cart_id=?", (cart_id,)) as cur:
            return [row[0] async for row in cur]


async def attach_cart_payment_proof(cart_id: str, file_id: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET payment_proof_file_id=?, status='payment_review' WHERE cart_id=?",
            (file_id, cart_id),
        )
        await db.commit()


# ---- Аренда: что у клиента сейчас арендовано и когда заканчивается ----

async def get_user_rent_orders(user_id: int) -> list[dict]:
    """Все оплаченные заказы аренды клиента (включая продления) — из них
    services/rent_extension.py собирает список действующих аренд."""
    status_placeholders = ",".join("?" for _ in PAID_STATUSES)
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT * FROM orders
                WHERE user_id = ? AND category = 'nft_rent'
                  AND status IN ({status_placeholders})
                ORDER BY id ASC""",
            [user_id, *PAID_STATUSES],
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ---- Напоминания о продлении Premium (см. services/premium_reminder.py) ----

async def get_premium_orders_due_for_reminder() -> list[dict]:
    """Заказы Premium 30-дневной давности, которым ещё не слали напоминание."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM orders
               WHERE category = 'premium'
                 AND status IN ('paid', 'fulfilling', 'completed')
                 AND (reminder_sent IS NULL OR reminder_sent = 0)
                 AND date(created_at) <= date('now', '-29 day')"""
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def mark_reminder_sent(order_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE orders SET reminder_sent = 1 WHERE id = ?", (order_id,))
        await db.commit()


# ---- Журнал автоплатежей с TON-кошелька (см. services/ton_wallet.py) ----

async def claim_ton_payment(order_id: int, purpose: str, amount_nano: int,
                            destination: str | None,
                            daily_cap_nano: int = 0) -> bool:
    """
    «Забронировать» оплату заказа ДО отправки транзакции.

    Возвращает False, если платёж по этой паре (заказ, назначение) уже
    начинали — значит, повторять нельзя. Именно эта строчка защищает от
    двойного списания при перезапуске бота, повторном нажатии кнопки или
    автоповторе после обрыва сети: вставка упадёт на UNIQUE-ограничении.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        try:
            # Дневной лимит считаем и бронируем в ОДНОЙ транзакции. Иначе два
            # заказа, пришедшие одновременно, оба видели бы «лимит ещё есть» и
            # оба уходили в сеть — касса уезжала за суточный потолок.
            await db.execute("BEGIN IMMEDIATE")
            if daily_cap_nano:
                async with db.execute(
                    """SELECT COALESCE(SUM(amount_nano), 0) FROM ton_payments
                       WHERE status IN ('sending', 'sent')
                         AND created_at >= datetime('now', 'start of day')"""
                ) as cur:
                    spent = (await cur.fetchone())[0] or 0
                if spent + amount_nano > daily_cap_nano:
                    await db.rollback()
                    return False
            await db.execute(
                """INSERT INTO ton_payments (order_id, purpose, amount_nano, destination, status)
                   VALUES (?, ?, ?, ?, 'sending')""",
                (order_id, purpose, amount_nano, destination),
            )
            await db.commit()
            return True
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
            return False  # уже есть такая пара или упёрлись в лимит


async def finish_ton_payment(order_id: int, purpose: str, ok: bool, error: str | None = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE ton_payments SET status = ?, error = ? WHERE order_id = ? AND purpose = ?",
            ("sent" if ok else "failed", (error or "")[:500] or None, order_id, purpose),
        )
        await db.commit()


async def release_ton_payment(order_id: int, purpose: str):
    """
    Снять бронь — только для случаев, когда транзакция ТОЧНО не ушла
    (не прошли проверки лимитов, кошелёк не настроен и т.п.). Если есть хоть
    малейший шанс, что транзакция улетела в сеть, бронь НЕ снимаем: лучше
    разобраться вручную, чем заплатить дважды.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM ton_payments WHERE order_id = ? AND purpose = ? AND status = 'sending'",
            (order_id, purpose),
        )
        await db.commit()


async def get_ton_spent_today_nano() -> int:
    """Сколько нанотонов уже списано (или в процессе списания) за сегодня."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            """SELECT COALESCE(SUM(amount_nano), 0) FROM ton_payments
               WHERE status != 'failed' AND date(created_at) = date('now')"""
        ) as cur:
            row = await cur.fetchone()
            return int(row[0] or 0)


async def get_ton_payments(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ton_payments ORDER BY id DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ---- Управление публичным рейтингом (см. /hidetop, /showtop) ----

async def hide_from_leaderboard(user_id: int, reason: str | None = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT INTO leaderboard_hidden (user_id, reason) VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET reason=excluded.reason""",
            (user_id, reason),
        )
        await db.commit()


async def unhide_from_leaderboard(user_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("DELETE FROM leaderboard_hidden WHERE user_id = ?", (user_id,))
        await db.commit()
        return cur.rowcount > 0


async def get_hidden_from_leaderboard() -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT h.user_id, h.reason, u.username, u.full_name
               FROM leaderboard_hidden h
               LEFT JOIN users u ON u.user_id = h.user_id
               ORDER BY h.created_at DESC"""
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def find_users_by_name(query: str) -> list[dict]:
    """
    Поиск клиента по @username, имени или числовому id — чтобы админу не
    приходилось выяснять user_id вручную. Возвращает несколько совпадений:
    имена в Telegram не уникальны, и выбрать нужного должен человек.
    """
    q = query.strip().lstrip("@")
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if q.isdigit():
            async with db.execute(
                "SELECT user_id, username, full_name FROM users WHERE user_id = ?", (int(q),)
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
                if rows:
                    return rows
        like = f"%{q}%"
        async with db.execute(
            """SELECT user_id, username, full_name FROM users
               WHERE username LIKE ? COLLATE NOCASE OR full_name LIKE ? COLLATE NOCASE
               LIMIT 10""",
            (like, like),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def find_orders_by_base_price(amount: int, within_hours: int = 24) -> list[dict]:
    """
    Неоплаченные заказы, у которых ЦЕНА равна этой сумме.

    Зачем отдельно от поиска по уникальной сумме: клиенты регулярно переводят
    круглую цену (11 000), проигнорировав просьбу отправить ровно 11 137.
    Деньги пришли, заказ есть, а автоподтверждение молчит — админ разбирается
    руками и гадает, чей это платёж.

    Возвращаем СПИСОК, а не один заказ, и подтверждать автоматически нельзя:
    у одной цены может быть несколько ожидающих заказов (два человека берут
    один пакет звёзд), и угадать, кто из них заплатил, невозможно. Решает
    админ — бот только показывает кандидатов.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        status_placeholders = ",".join("?" for _ in UNPAID_STATUSES)
        async with db.execute(
            f"""SELECT * FROM orders WHERE status IN ({status_placeholders})
                AND price_uzs = ?
                AND created_at >= datetime('now', '-{int(within_hours)} hours')
                ORDER BY id DESC LIMIT 5""",
            (*UNPAID_STATUSES, amount),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    # Корзина — несколько строк с одной суммой: показываем её как ОДНУ позицию,
    # иначе пять товаров выглядят как пять разных кандидатов, и админ остаётся
    # без кнопки подтверждения на совершенно обычном платеже.
    seen_carts = set()
    unique = []
    for r in rows:
        cart_id = r.get("cart_id")
        if cart_id:
            if cart_id in seen_carts:
                continue
            seen_carts.add(cart_id)
        unique.append(r)
    return unique


async def find_underpaid_orders(amount: int, max_gap: int, within_hours: int = 24) -> list[dict]:
    """
    Заказы, которым этого поступления НЕ ХВАТИЛО совсем чуть-чуть.

    Живой случай: заказу выдана сумма 11 207, а человек перевёл 11 000 или
    11 100 — округлил, как привык. Деньги реально пришли, заказ висит, а
    автоподтверждение молчит, потому что сумма не совпала до сума.

    Ищем неоплаченные заказы, где ожидаемая сумма БОЛЬШЕ пришедшей, но
    разница не больше max_gap. Так под выборку попадает недоплата на размер
    надбавки (и круглая цена тоже — она частный случай), но не попадает
    чужой платёж на совсем другую сумму.

    Возвращаем СПИСОК: если кандидатов несколько, угадать, кто именно
    заплатил, нельзя — решать будет админ.
    """
    if max_gap <= 0:
        return []
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        status_placeholders = ",".join("?" for _ in UNPAID_STATUSES)
        async with db.execute(
            f"""SELECT * FROM orders
                WHERE status IN ({status_placeholders})
                  AND expected_amount_uzs IS NOT NULL
                  AND expected_amount_uzs > ?
                  AND expected_amount_uzs - ? <= ?
                  AND created_at >= datetime('now', ?)
                ORDER BY id DESC
                LIMIT 5""",
            (*UNPAID_STATUSES, amount, amount, max_gap, f"-{int(within_hours)} hours"),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    # Корзина — это несколько строк заказов с ОДНОЙ суммой. Схлопываем её в
    # одну позицию, иначе админ увидит пять одинаковых кандидатов вместо одного.
    seen_carts = set()
    unique = []
    for r in rows:
        cart_id = r.get("cart_id")
        if cart_id:
            if cart_id in seen_carts:
                continue
            seen_carts.add(cart_id)
        unique.append(r)
    return unique


# ---- Защита от повторного использования одного чека ----

async def find_order_by_receipt(fingerprint: str, exclude_order_id: int | None = None,
                                exclude_cart_id: str | None = None) -> dict | None:
    """
    Не присылали ли ЭТОТ ЖЕ чек раньше, по другому заказу?

    Зачем: один скриншот перевода ходит по рукам. Человек оформляет заказ,
    платит один раз, а потом шлёт тот же чек ещё и ещё — под каждый новый
    заказ. Бывает и так, что чек пересылают знакомому, и тот прикладывает
    чужой платёж к своему заказу. Снаружи это выглядит как поток честных
    заказов, а деньги приходили один раз.

    Отпечаток: у фото из чата это file_unique_id (у одного и того же файла он
    не меняется, сколько ни пересылай), у чека из витрины — хэш картинки.

    Свой же заказ исключаем: человек имеет право переотправить чек, если
    первый раз не прошёл.
    """
    if not fingerprint:
        return None
    query = "SELECT * FROM orders WHERE receipt_fingerprint = ?"
    params: list = [fingerprint]
    if exclude_order_id:
        query += " AND id != ?"
        params.append(exclude_order_id)
    if exclude_cart_id:
        query += " AND (cart_id IS NULL OR cart_id != ?)"
        params.append(exclude_cart_id)
    query += " ORDER BY id LIMIT 1"

    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_receipt_fingerprint(order_id: int, fingerprint: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET receipt_fingerprint = ? WHERE id = ?", (fingerprint, order_id)
        )
        await db.commit()


async def set_cart_receipt_fingerprint(cart_id: str, fingerprint: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET receipt_fingerprint = ? WHERE cart_id = ?", (fingerprint, cart_id)
        )
        await db.commit()


async def count_pending_orders(user_id: int) -> int:
    """
    Сколько у клиента заказов, которые ещё ждут оплаты или проверки.

    Нужно, чтобы один человек не мог наплодить десяток заявок и завалить
    админа: пока предыдущие не закрыты, новые оформлять незачем.
    Корзина считается за один заказ — иначе покупка пяти товаров сразу
    упёрлась бы в лимит на ровном месте.

    Считаем ТОЛЬКО заказы за последние сутки. Это страховка от самого
    неприятного сценария: если фоновая чистка просроченных заказов почему-то
    не отработает, старые "висяки" не должны навсегда закрыть человеку
    возможность покупать — на рекламном трафике это прямая потеря клиентов.
    """
    status_placeholders = ",".join("?" for _ in UNPAID_STATUSES)
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            f"""SELECT COUNT(*) FROM (
                    SELECT COALESCE(cart_id, CAST(id AS TEXT)) AS grp
                    FROM orders
                    WHERE user_id = ? AND status IN ({status_placeholders})
                      AND created_at >= datetime('now', '-1 day')
                    GROUP BY grp
                )""",
            (user_id, *UNPAID_STATUSES),
        ) as cur:
            return (await cur.fetchone())[0] or 0


# ---- Карточки чеков у админа ----

async def remember_admin_card(order_ids, chat_id: int, message_id: int, caption: str):
    """Запомнить, каким сообщением показана карточка чека — чтобы потом его дополнить."""
    ids = [order_ids] if isinstance(order_ids, int) else list(order_ids)
    async with aiosqlite.connect(config.DB_PATH) as db:
        for order_id in ids:
            await db.execute(
                """INSERT INTO admin_cards (order_id, chat_id, message_id, caption, notes)
                   VALUES (?, ?, ?, ?, '')
                   ON CONFLICT(order_id, chat_id) DO UPDATE SET
                     message_id=excluded.message_id, caption=excluded.caption, notes=''""",
                (order_id, chat_id, message_id, caption[:3000]),
            )
        await db.commit()


async def add_admin_card_note(order_id: int, note: str) -> list[dict]:
    """
    Куда отправить итог по заказу — и не отправляли ли мы его уже.

    Возвращает [{chat_id, message_id}] карточек, которым этот итог ещё не
    писали. Товары одной корзины закрываются по одному, и без этой проверки
    «ВЫПОЛНЕНО» прилетело бы столько раз, сколько в корзине товаров.
    """
    out = []
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM admin_cards WHERE order_id = ?", (order_id,)
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
        for r in rows:
            if note in (r["notes"] or ""):
                continue
            await db.execute(
                "UPDATE admin_cards SET notes = ? WHERE order_id = ? AND chat_id = ?",
                ((r["notes"] or "") + note, order_id, r["chat_id"]),
            )
            out.append({"chat_id": r["chat_id"], "message_id": r["message_id"]})
        await db.commit()
    return out


async def find_user_id_by_username(username: str) -> int | None:
    """
    Найти user_id получателя по @username — в НАШЕЙ базе.

    Telegram не даёт боту превратить @username в user_id: метода для этого
    в Bot API просто нет, а get_chat() для обычных пользователей срабатывает
    далеко не всегда. Зато если человек хоть раз нажимал /start, его id у нас
    уже есть — раньше мы туда не заглядывали и отказывали в выполнении заказа
    людям, которые бота давно запустили.

    Регистр не важен: клиент пишет «@Bunny_00P», а в базе лежит «bunny_00p».
    """
    uname = (username or "").strip().lstrip("@").lower()
    if not uname:
        return None

    async with aiosqlite.connect(config.DB_PATH) as db:
        # 1) Наши пользователи — самый надёжный источник.
        async with db.execute(
            "SELECT user_id FROM users WHERE LOWER(username) = ? ORDER BY user_id DESC LIMIT 1",
            (uname,),
        ) as cur:
            row = await cur.fetchone()
            if row:
                return int(row[0])

        # 2) Получатели прошлых заказов, у которых id уже был известен
        #    (например, человек получал подарок «себе» со своего же аккаунта).
        async with db.execute(
            """SELECT recipient_user_id FROM orders
               WHERE recipient_user_id IS NOT NULL
                 AND LOWER(REPLACE(recipient, '@', '')) = ?
               ORDER BY id DESC LIMIT 1""",
            (uname,),
        ) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                return int(row[0])
    return None


# ---- Доплата по недоплаченному заказу ----

async def remember_topup(order_id: int, amount: int):
    """
    Запомнить, что по заказу ждём ДОПЛАТУ на такую сумму.

    Без этого обещание «доплатите — заказ продолжится сам» было бы ложью:
    отдельный перевод на 207 сум не совпадает ни с ценой, ни с суммой заказа,
    и бот просто не понял бы, что это за деньги.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT INTO pending_topups (amount, order_id) VALUES (?, ?)
               ON CONFLICT(amount) DO UPDATE SET
                 order_id=excluded.order_id, created_at=CURRENT_TIMESTAMP""",
            (amount, order_id),
        )
        await db.commit()


async def find_topup_order(amount: int, hours: int = 24) -> dict | None:
    """Заказ, которому не хватало ровно этой суммы (и он всё ещё ждёт оплаты)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        status_placeholders = ",".join("?" for _ in UNPAID_STATUSES)
        async with db.execute(
            f"""SELECT o.* FROM pending_topups p
                JOIN orders o ON o.id = p.order_id
                WHERE p.amount = ?
                  AND p.created_at >= datetime('now', '-{int(hours)} hours')
                  AND o.status IN ({status_placeholders})
                LIMIT 1""",
            (amount, *UNPAID_STATUSES),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def clear_topup(order_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM pending_topups WHERE order_id = ?", (order_id,))
        await db.commit()


# ---- Баланс клиента ----

async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(balance_uzs, 0) FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def credit_balance(user_id: int, amount: int, reason: str, order_id: int | None = None) -> int:
    """Зачислить на баланс. Возвращает новый остаток."""
    if amount <= 0:
        return await get_balance(user_id)
    async with aiosqlite.connect(config.DB_PATH) as db:
        try:
            await db.execute("BEGIN IMMEDIATE")
            # Строки пользователя может не быть: в витрину можно попасть по
            # прямой ссылке, ни разу не нажав /start. Без этой вставки UPDATE
            # не находил кого обновлять, деньги "зачислялись" в никуда, и
            # достать их обратно было нечем — клиент платил, баланс 0.
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, '', '')",
                (user_id,),
            )
            await db.execute(
                "UPDATE users SET balance_uzs = COALESCE(balance_uzs, 0) + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await db.execute(
                "INSERT INTO balance_txns (user_id, delta_uzs, reason, order_id) VALUES (?, ?, ?, ?)",
                (user_id, amount, reason, order_id),
            )
            async with db.execute(
                "SELECT COALESCE(balance_uzs, 0) FROM users WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
            await db.commit()
            return int(row[0]) if row else 0
        except Exception:
            await db.rollback()
            raise


async def debit_balance(user_id: int, amount: int, reason: str, order_id: int | None = None) -> bool:
    """
    Списать с баланса. False — денег не хватило, НИЧЕГО не списано.

    Проверка остатка и списание идут одной транзакцией: иначе два заказа,
    оформленных одновременно, оба увидели бы «денег хватает» и ушли в минус.
    """
    if amount <= 0:
        return True
    async with aiosqlite.connect(config.DB_PATH) as db:
        # BEGIN внутри try: под нагрузкой sqlite отдаёт "database is locked",
        # и снаружи try это исключение улетало мимо перехвата — клиент видел
        # "ошибка сети" на оплате и не понимал, списались деньги или нет.
        try:
            await db.execute("BEGIN IMMEDIATE")
            async with db.execute(
                "SELECT COALESCE(balance_uzs, 0) FROM users WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
            if not row or int(row[0]) < amount:
                await db.rollback()
                return False
            await db.execute(
                "UPDATE users SET balance_uzs = balance_uzs - ? WHERE user_id = ?",
                (amount, user_id),
            )
            await db.execute(
                "INSERT INTO balance_txns (user_id, delta_uzs, reason, order_id) VALUES (?, ?, ?, ?)",
                (user_id, -amount, reason, order_id),
            )
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False


async def pay_order_from_balance(order_id: int, user_id: int, amount: int,
                                 cart_id: str | None = None) -> str:
    """
    Оплатить заказ с баланса ОДНОЙ транзакцией: проверка статуса, списание
    и перевод заказа в «оплачен» — вместе или никак.

    -> "ok" | "wrong_status" | "insufficient" | "busy"

    Почему так, а не тремя шагами: между проверкой и списанием есть await, и
    клиент, тапнувший кнопку трижды, проходил проверку трижды. Деньги
    списывались три раза, а заказ выполнялся три раза — за счёт магазина.
    Тут же заказ ещё и «занимается» сменой статуса, поэтому второй запрос
    видит его уже не awaiting_payment и уходит ни с чем.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        try:
            await db.execute("BEGIN IMMEDIATE")

            if cart_id:
                async with db.execute(
                    "SELECT COUNT(*) FROM orders WHERE cart_id = ? AND status != 'awaiting_payment'",
                    (cart_id,),
                ) as cur:
                    wrong = (await cur.fetchone())[0]
                if wrong:
                    await db.rollback()
                    return "wrong_status"
            else:
                async with db.execute(
                    "SELECT status FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id)
                ) as cur:
                    row = await cur.fetchone()
                if not row or row[0] != "awaiting_payment":
                    await db.rollback()
                    return "wrong_status"

            async with db.execute(
                "SELECT COALESCE(balance_uzs, 0) FROM users WHERE user_id = ?", (user_id,)
            ) as cur:
                brow = await cur.fetchone()
            if not brow or int(brow[0]) < amount:
                await db.rollback()
                return "insufficient"

            await db.execute(
                "UPDATE users SET balance_uzs = balance_uzs - ? WHERE user_id = ?",
                (amount, user_id),
            )
            label = f"корзина {cart_id}" if cart_id else f"заказ #{order_id}"
            await db.execute(
                "INSERT INTO balance_txns (user_id, delta_uzs, reason, order_id) VALUES (?, ?, ?, ?)",
                (user_id, -amount, f"Оплата: {label}", order_id),
            )
            if cart_id:
                await db.execute(
                    "UPDATE orders SET status = 'paid' WHERE cart_id = ? AND status = 'awaiting_payment'",
                    (cart_id,),
                )
            else:
                await db.execute(
                    "UPDATE orders SET status = 'paid' WHERE id = ? AND status = 'awaiting_payment'",
                    (order_id,),
                )
            await db.commit()
            return "ok"
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            print(f"[BALANCE] оплата заказа {order_id} сорвалась: {e}", flush=True)
            return "busy"


async def refund_to_balance(user_id: int, amount: int, reason: str, order_id: int | None = None) -> int:
    """Вернуть деньги на баланс — когда списали, а выполнить не смогли."""
    return await credit_balance(user_id, amount, reason, order_id)


async def get_balance_history(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM balance_txns WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ---- Заявки на пополнение ----

async def create_topup_request(user_id: int, base_amount: int, max_offset: int) -> dict:
    """
    Создать заявку на пополнение и выдать сумму с уникальным хвостом.

    Хвост нужен ровно для одного: опознать перевод. SMS от банка говорит
    сумму, но не отправителя, и без уникальной суммы понять, чьи это деньги,
    невозможно. Сумма подбирается так, чтобы не совпасть ни с другой заявкой,
    ни с суммой какого-нибудь ждущего оплаты заказа.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            amount = await _pick_free_amount(base_amount, max_offset, db)
            cur = await db.execute(
                "INSERT INTO topup_requests (user_id, expected_uzs) VALUES (?, ?)",
                (user_id, amount),
            )
            await db.commit()
            return {"id": cur.lastrowid, "expected": amount, "base": base_amount}
        except Exception:
            await db.rollback()
            raise


TOPUP_OVERPAY_SLACK = 50  # на столько пришедшее может превысить ожидаемое


async def find_topup_requests(amount: int, tolerance: int, hours: int = 24) -> list[dict]:
    """
    Заявки на пополнение, под которые подходит это поступление.

    Ищем с допуском ВНИЗ: банк удерживает комиссию, поэтому на карту приходит
    не больше ожидаемого, а меньше. Сверху тоже даём небольшой запас — люди
    иногда округляют вверх.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT * FROM topup_requests
                WHERE status = 'pending'
                  AND expected_uzs - ? BETWEEN ? AND ?
                  AND created_at >= datetime('now', '-{int(hours)} hours')
                ORDER BY ABS(expected_uzs - ?) ASC, id DESC
                LIMIT 5""",
            # Вниз — на размер комиссии банка, вверх — почти ноль.
            # Комиссия может только УМЕНЬШИТЬ пришедшую сумму. Симметричный
            # допуск ловил чужие платежи: перевод на 11 000 по заказу
            # «прилипал» к пополнению, ожидавшему 10 437, и деньги уходили
            # не тому человеку.
            (amount, -TOPUP_OVERPAY_SLACK, tolerance, amount),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def find_topup_by_receipt(fingerprint: str, exclude_id: int | None = None) -> dict | None:
    """Этот же чек уже присылали по другому пополнению?"""
    if not fingerprint:
        return None
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM topup_requests WHERE receipt_fp = ?"
        params: list = [fingerprint]
        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)
        query += " ORDER BY id DESC LIMIT 1"
        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_topup_receipt(topup_id: int, fingerprint: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE topup_requests SET receipt_fp = ? WHERE id = ?", (fingerprint, topup_id)
        )
        await db.commit()


async def close_topup_request(topup_id: int, credited: int) -> bool:
    """
    Закрыть заявку. False — её уже закрыли, зачислять НЕЛЬЗЯ.

    Это замок, а не пометка: зачисление делается ТОЛЬКО после того, как эта
    функция вернула True. Иначе одно поступление легко превращалось в два
    зачисления — SMS продублировалась, или два админа нажали кнопку каждый в
    своём чате, и магазин дарил клиентам деньги из воздуха.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "UPDATE topup_requests SET status = 'done', credited_uzs = ? "
            "WHERE id = ? AND status = 'pending'",
            (credited, topup_id),
        )
        await db.commit()
        return cur.rowcount == 1


async def cancel_topup_request(user_id: int) -> bool:
    """Отменить своё незакрытое пополнение — чтобы заказать другую сумму."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "UPDATE topup_requests SET status = 'cancelled' "
            "WHERE user_id = ? AND status = 'pending'",
            (user_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_pending_topup_by_id(topup_id: int) -> dict | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM topup_requests WHERE id = ? AND status = 'pending'", (topup_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_pending_topup(user_id: int) -> dict | None:
    """Последняя незакрытая заявка клиента — её показывает витрина."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM topup_requests
               WHERE user_id = ? AND status = 'pending'
                 AND created_at >= datetime('now', '-24 hours')
               ORDER BY id DESC LIMIT 1""",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_open_orders() -> list[dict]:
    """
    Все незакрытые заказы — для массового закрытия командой /closeall.

    Делим их по смыслу: оплаченные (их владелец уже выполнил руками) и
    неоплаченные (их надо отменить, а не объявлять выполненными — иначе
    человек, который так и не заплатил, получит «ваш заказ готов»).
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM orders
               WHERE status IN ('awaiting_payment', 'payment_review', 'paid', 'fulfilling')
               ORDER BY id"""
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ---- Бан клиентов ----

async def ban_user(user_id: int, username: str | None, reason: str | None, banned_by: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT INTO banned_users (user_id, username, reason, banned_by)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username=excluded.username, reason=excluded.reason, banned_by=excluded.banned_by""",
            (user_id, username, reason, banned_by),
        )
        await db.commit()


async def unban_user(user_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        await db.commit()
        return cur.rowcount > 0


async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone() is not None


async def get_banned_users() -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, u.full_name FROM banned_users b
               LEFT JOIN users u ON u.user_id = b.user_id
               ORDER BY b.created_at DESC"""
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def find_expired_order_by_amount(amount: int, hours: int = 24) -> dict | None:
    """
    Заказ, который отменился по таймауту, но сумма совпадает с поступлением.

    Клиент нередко платит позже, чем мы ждали: пошёл к терминалу, банк задержал
    SMS, отвлёкся. Раньше такой заказ просто закрывался, деньги приходили в
    пустоту, и ни клиент, ни админ об этом не узнавали. Теперь бот показывает
    такое поступление админу — подтвердить можно одной кнопкой.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT * FROM orders
                WHERE status = 'rejected' AND expected_amount_uzs = ?
                  AND admin_comment = '{TIMEOUT_COMMENT}'
                  AND created_at >= datetime('now', '-{int(hours)} hours')
                ORDER BY id DESC LIMIT 1""",
            (amount,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
