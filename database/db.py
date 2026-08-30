import aiosqlite
import config

CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    category TEXT NOT NULL,          -- stars | premium | nft_rent
    item_name TEXT NOT NULL,         -- напр. "100 звёзд", "Premium 3 мес", "Plush Pepe"
    quantity INTEGER DEFAULT 1,
    price_uzs INTEGER NOT NULL,
    recipient TEXT,                  -- @username или ссылка, куда доставить звёзды/подарок
    rent_days INTEGER,               -- только для аренды NFT
    nft_address TEXT,                -- адрес NFT на MarketApp (для аренды)
    base_price_per_day_gram TEXT,    -- базовая цена/день в GRAM (для аренды)
    status TEXT DEFAULT 'awaiting_payment',
    -- awaiting_payment -> payment_review -> paid -> fulfilling -> completed / rejected
    payment_proof_file_id TEXT,
    admin_comment TEXT,
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
