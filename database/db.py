import os
import re
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
import aiosqlite
import asyncpg
from config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path("dokon_hisobi.db").absolute()
_pg_pool: Optional[asyncpg.Pool] = None

def is_postgres() -> bool:
    """PostgreSQL yoki Supabase ishlatilayotganini tekshirish"""
    db_url = getattr(settings, "DATABASE_URL", "")
    return db_url.startswith("postgresql://") or db_url.startswith("postgres://")

async def get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://"):]
        _pg_pool = await asyncpg.create_pool(
            db_url,
            min_size=3,
            max_size=20,
            command_timeout=30,
            statement_cache_size=0
        )
    return _pg_pool

def adapt_query_for_pg(sql: str) -> str:
    """SQLite SQL sintaksisini PostgreSQL ga moslashtirish"""
    # 1. ? belgilarini $1, $2, $3 ga almashtirish
    parts = sql.split('?')
    if len(parts) > 1:
        res = parts[0]
        for i in range(1, len(parts)):
            res += f"${i}" + parts[i]
        sql = res

    # 2. SQLite sana funksiyalarini PostgreSQL ga almashtirish
    sql = re.sub(r"DATE\('now',\s*'\+7 days'\)", "(CURRENT_DATE + INTERVAL '7 days')", sql, flags=re.IGNORECASE)
    sql = re.sub(r"DATE\('now',\s*'-30 days'\)", "(CURRENT_DATE - INTERVAL '30 days')", sql, flags=re.IGNORECASE)
    sql = re.sub(r"DATE\('now'\)", "CURRENT_DATE", sql, flags=re.IGNORECASE)
    
    return sql

from decimal import Decimal
from datetime import date, datetime

def clean_row(r: dict) -> dict:
    """Decimal va date turlarini JSON uchun qulay qilish"""
    res = {}
    for k, v in r.items():
        if isinstance(v, Decimal):
            res[k] = float(v)
        elif isinstance(v, (date, datetime)):
            res[k] = v.isoformat()
        else:
            res[k] = v
    return res

async def db_fetch_all(query: str, *params) -> List[dict]:
    """Barcha natijalarni ro'yxat ko'rinishida olish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            pg_query = adapt_query_for_pg(query)
            rows = await conn.fetch(pg_query, *params)
            return [clean_row(dict(r)) for r in rows]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [clean_row(dict(r)) for r in rows]

async def db_fetch_one(query: str, *params) -> Optional[dict]:
    """Bitta yozuvni olish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            pg_query = adapt_query_for_pg(query)
            row = await conn.fetchrow(pg_query, *params)
            return clean_row(dict(row)) if row else None
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return clean_row(dict(row)) if row else None

async def db_execute(query: str, *params) -> Any:
    """SQL komandasini bajarish (UPDATE, DELETE, INSERT)"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            pg_query = adapt_query_for_pg(query)
            return await conn.execute(pg_query, *params)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor

async def db_execute_insert(query: str, *params) -> int:
    """INSERT qilib, yangi ID sini qaytarish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            # Agar RETURNING id bo'lmasa, qo'shamiz
            pg_query = adapt_query_for_pg(query)
            if "RETURNING" not in pg_query.upper():
                pg_query = pg_query.rstrip(" ;") + " RETURNING id"
            return await conn.fetchval(pg_query, *params)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.lastrowid

async def init_db():
    """Ma'lumotlar bazasini yaratish (PostgreSQL/Supabase yoki SQLite)"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    shop_name TEXT NOT NULL,
                    shop_id TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                );

                CREATE TABLE IF NOT EXISTS customers (
                    id SERIAL PRIMARY KEY,
                    shop_id TEXT NOT NULL REFERENCES admins(shop_id),
                    full_name TEXT NOT NULL,
                    phone TEXT,
                    telegram_id BIGINT,
                    notes TEXT,
                    total_debt NUMERIC(15, 2) DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(shop_id, phone)
                );

                CREATE TABLE IF NOT EXISTS debts (
                    id SERIAL PRIMARY KEY,
                    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                    shop_id TEXT NOT NULL REFERENCES admins(shop_id),
                    amount NUMERIC(15, 2) NOT NULL CHECK(amount > 0),
                    description TEXT DEFAULT 'Nasiya savdo',
                    debt_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    due_date DATE NOT NULL,
                    status VARCHAR(20) DEFAULT 'active' CHECK(status IN ('active','paid','overdue')),
                    paid_date TIMESTAMP WITH TIME ZONE,
                    paid_amount NUMERIC(15, 2),
                    screenshot_url TEXT,
                    reminder_sent BOOLEAN DEFAULT FALSE,
                    admin_note TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS notifications_log (
                    id SERIAL PRIMARY KEY,
                    debt_id INTEGER NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
                    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                    type VARCHAR(30) CHECK(type IN ('reminder_1day','reminder_3day','overdue','manual')),
                    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS payment_history (
                    id SERIAL PRIMARY KEY,
                    debt_id INTEGER NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
                    amount NUMERIC(15, 2) NOT NULL,
                    paid_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    note TEXT,
                    admin_id BIGINT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_customers_shop ON customers(shop_id);
                CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
                CREATE INDEX IF NOT EXISTS idx_debts_customer ON debts(customer_id);
                CREATE INDEX IF NOT EXISTS idx_debts_shop ON debts(shop_id);
                CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);
                CREATE INDEX IF NOT EXISTS idx_debts_due_date ON debts(due_date);

                ALTER TABLE customers ALTER COLUMN phone DROP NOT NULL;
                ALTER TABLE debts ALTER COLUMN description DROP NOT NULL;
                ALTER TABLE debts ADD COLUMN IF NOT EXISTS created_by_admin_id BIGINT;
                ALTER TABLE debts ADD COLUMN IF NOT EXISTS created_by_admin_name TEXT;
                ALTER TABLE payment_history ADD COLUMN IF NOT EXISTS admin_name TEXT;
            """)
        logger.info("✅ Supabase / PostgreSQL ma'lumotlar bazasi tayyorlandi")
    else:
        # SQLite
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    shop_name TEXT NOT NULL,
                    shop_id TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                );
                
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shop_id TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    phone TEXT,
                    telegram_id BIGINT,
                    notes TEXT,
                    total_debt REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (shop_id) REFERENCES admins(shop_id),
                    UNIQUE(shop_id, phone)
                );
                
                CREATE TABLE IF NOT EXISTS debts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    shop_id TEXT NOT NULL,
                    amount REAL NOT NULL CHECK(amount > 0),
                    description TEXT DEFAULT 'Nasiya savdo',
                    debt_date DATE NOT NULL DEFAULT (DATE('now')),
                    due_date DATE NOT NULL,
                    status TEXT DEFAULT 'active' CHECK(status IN ('active','paid','overdue')),
                    paid_date DATETIME,
                    paid_amount REAL,
                    screenshot_url TEXT,
                    reminder_sent BOOLEAN DEFAULT FALSE,
                    admin_note TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id),
                    FOREIGN KEY (shop_id) REFERENCES admins(shop_id)
                );
                
                CREATE TABLE IF NOT EXISTS notifications_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    debt_id INTEGER NOT NULL,
                    customer_id INTEGER NOT NULL,
                    type TEXT CHECK(type IN ('reminder_1day','reminder_3day','overdue','manual')),
                    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    FOREIGN KEY (debt_id) REFERENCES debts(id),
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                );
                
                CREATE TABLE IF NOT EXISTS payment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    debt_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    paid_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    note TEXT,
                    admin_id BIGINT NOT NULL,
                    FOREIGN KEY (debt_id) REFERENCES debts(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_customers_shop ON customers(shop_id);
                CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
                CREATE INDEX IF NOT EXISTS idx_debts_customer ON debts(customer_id);
                CREATE INDEX IF NOT EXISTS idx_debts_shop ON debts(shop_id);
                CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);
                CREATE INDEX IF NOT EXISTS idx_debts_due_date ON debts(due_date);
            """)
            await db.commit()
        logger.info("✅ SQLite ma'lumotlar bazasi tayyorlandi")

async def get_db():
    """DB ulanishini qaytaradi (legacy)"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db
