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
        # Миграции для баз, созданных до появления этих полей/таблиц
        for stmt in (
            "ALTER TABLE users ADD COLUMN language TEXT",
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
UNIQUE_AMOUNT_ORDER_TTL_MINUTES = 30


async def allocate_unique_amount(base_price_uzs: int, max_offset: int = DEFAULT_MAX_AMOUNT_OFFSET) -> int:
    """
    Возвращает base_price_uzs + небольшую случайную надбавку (1..max_offset),
    гарантированно не совпадающую с суммой ни одного другого сейчас неоплаченного
    заказа — чтобы по входящей SMS с суммой X можно было однозначно понять,
    какой именно заказ оплатили, даже если все клиенты платят на одну и ту же
    личную карту.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        status_placeholders = ",".join("?" for _ in UNPAID_STATUSES)
        async with db.execute(
            f"SELECT expected_amount_uzs FROM orders WHERE status IN ({status_placeholders}) "
            "AND expected_amount_uzs IS NOT NULL",
            UNPAID_STATUSES,
        ) as cur:
            taken = {row[0] async for row in cur}

    candidates = [
        base_price_uzs + offset
        for offset in range(1, max_offset + 1)
        if (base_price_uzs + offset) not in taken
    ]
    if not candidates:
        # Практически нереально при разумном max_offset, но на всякий случай —
        # не роняем оформление заказа, просто без анти-коллизийной надбавки.
        return base_price_uzs
    return random.choice(candidates)


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
                f"UPDATE orders SET status='rejected', admin_comment='Истекло время оплаты' "
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


async def get_leaderboard(since_sql: str | None, limit: int = 20) -> list[dict]:
    """
    Топ клиентов по сумме трат (для вкладки "TOP"). since_sql=None — за всё время.
    -> [{"user_id": int, "username": str|None, "full_name": str|None,
         "total_uzs": int, "orders_count": int}]
    """
    status_placeholders = ",".join("?" for _ in PAID_STATUSES)
    where = f"o.status IN ({status_placeholders})"
    params: list = list(PAID_STATUSES)
    if since_sql:
        where += " AND o.created_at >= ?"
        params.append(since_sql)
    # Скрытые вручную аккаунты (см. /hidetop) в публичный рейтинг не попадают
    where += " AND o.user_id NOT IN (SELECT user_id FROM leaderboard_hidden)"
    params.append(limit)

    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT o.user_id, u.username, u.full_name,
                       SUM(o.price_uzs) AS total_uzs, COUNT(*) AS orders_count
                FROM orders o
                LEFT JOIN users u ON u.user_id = o.user_id
                WHERE {where}
                GROUP BY o.user_id
                ORDER BY total_uzs DESC
                LIMIT ?""",
            params,
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


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
                            destination: str | None) -> bool:
    """
    «Забронировать» оплату заказа ДО отправки транзакции.

    Возвращает False, если платёж по этой паре (заказ, назначение) уже
    начинали — значит, повторять нельзя. Именно эта строчка защищает от
    двойного списания при перезапуске бота, повторном нажатии кнопки или
    автоповторе после обрыва сети: вставка упадёт на UNIQUE-ограничении.
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        try:
            await db.execute(
                """INSERT INTO ton_payments (order_id, purpose, amount_nano, destination, status)
                   VALUES (?, ?, ?, ?, 'sending')""",
                (order_id, purpose, amount_nano, destination),
            )
            await db.commit()
            return True
        except Exception:
            return False  # уже есть такая пара — платёж повторять нельзя


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
