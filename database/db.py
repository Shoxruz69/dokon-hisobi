import aiosqlite
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("dokon_hisobi.db").absolute()

async def init_db():
    """Ma'lumotlar bazasini yaratish va jadvallarni boshlash"""
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
                phone TEXT NOT NULL,
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
                description TEXT NOT NULL,
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
            
            /* Indekslar — tezkor qidiruv */
            CREATE INDEX IF NOT EXISTS idx_customers_shop ON customers(shop_id);
            CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
            CREATE INDEX IF NOT EXISTS idx_debts_customer ON debts(customer_id);
            CREATE INDEX IF NOT EXISTS idx_debts_shop ON debts(shop_id);
            CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);
            CREATE INDEX IF NOT EXISTS idx_debts_due_date ON debts(due_date);
        """)
        await db.commit()
    logger.info("✅ Ma'lumotlar bazasi tayyorlandi")

async def get_db():
    """DB ulanishini qaytaradi"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db
