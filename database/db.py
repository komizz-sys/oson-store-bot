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


async def init_db():
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(CREATE_USERS_TABLE)
        await db.execute(CREATE_ORDERS_TABLE)
        await db.execute(CREATE_SUPPORT_TABLE)
        # Миграции для баз, созданных до появления этих полей/таблиц
        for stmt in (
            "ALTER TABLE users ADD COLUMN language TEXT",
            "ALTER TABLE users ADD COLUMN last_seen TEXT",
            "ALTER TABLE orders ADD COLUMN content_video_url TEXT",
            "ALTER TABLE orders ADD COLUMN content_text TEXT",
            "ALTER TABLE orders ADD COLUMN recipient_user_id INTEGER",
            "ALTER TABLE orders ADD COLUMN rent_link TEXT",
            "ALTER TABLE orders ADD COLUMN expected_amount_uzs INTEGER",
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
    Доход по категориям за период (или за всё время, если since_sql=None).
    Для аренды (nft_rent) также считает реальный расход на MarketApp —
    он известен точно: base_price_per_day_gram * rent_days, переведённый
    в сум по ТЕКУЩЕМУ курсу (курс на момент самой аренды не хранится,
    так что при сильном изменении курса цифра будет чуть приблизительной).
    -> {
        "income_by_category": {"stars": int, "premium": int, "simple_gift": int, "nft_rent": int},
        "income_total": int,
        "orders_count": int,
        "rent_auto_cost_uzs": int,
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

        async with db.execute(
            f"""SELECT COALESCE(SUM(CAST(base_price_per_day_gram AS REAL) * rent_days), 0)
                FROM orders WHERE {where} AND category = 'nft_rent'
                AND base_price_per_day_gram IS NOT NULL AND rent_days IS NOT NULL""",
            params,
        ) as cur:
            rent_gram_total = (await cur.fetchone())[0] or 0

    income_by_category = {row[0]: row[1] for row in rows}
    orders_count = sum(row[2] for row in rows)
    income_total = sum(income_by_category.values())
    rent_auto_cost_uzs = round(rent_gram_total * ton_gram_rate_uzs)

    return {
        "income_by_category": income_by_category,
        "income_total": income_total,
        "orders_count": orders_count,
        "rent_auto_cost_uzs": rent_auto_cost_uzs,
    }


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
