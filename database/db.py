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


async def init_db():
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(CREATE_USERS_TABLE)
        await db.execute(CREATE_ORDERS_TABLE)
        # Миграция для баз, созданных до появления языка пользователя
        try:
            await db.execute("ALTER TABLE users ADD COLUMN language TEXT")
        except Exception:
            pass  # колонка уже есть
        await db.commit()


async def upsert_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name""",
            (user_id, username, full_name),
        )
        await db.commit()


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
