import aiosqlite
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from .db import DB_PATH

logger = logging.getLogger(__name__)

# ============================================================
# ADMIN QUERIES
# ============================================================

async def get_admin_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Adminni telegram_id bo'yicha olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM admins WHERE telegram_id = ? AND is_active = TRUE",
            (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

        # Agar settings.ADMIN_TELEGRAM_ID ga to'g'ri kelsa
        from config import settings
        if telegram_id == settings.ADMIN_TELEGRAM_ID:
            async with db.execute("SELECT * FROM admins WHERE is_active = TRUE ORDER BY id ASC LIMIT 1") as cur:
                first = await cur.fetchone()
                if first:
                    await db.execute("UPDATE admins SET telegram_id = ? WHERE id = ?", (telegram_id, first["id"]))
                    await db.commit()
                    return dict(first)
                else:
                    shop_id = "5832B1F2"
                    await db.execute(
                        "INSERT INTO admins (telegram_id, full_name, shop_name, shop_id) VALUES (?, ?, ?, ?)",
                        (telegram_id, "Do'kon Egasi", "Shox Market", shop_id)
                    )
                    await db.commit()
                    return {
                        "telegram_id": telegram_id,
                        "full_name": "Do'kon Egasi",
                        "shop_name": "Shox Market",
                        "shop_id": shop_id
                    }
    return None

async def get_admin_by_shop_id(shop_id: str) -> Optional[dict]:
    """Adminni shop_id bo'yicha olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM admins WHERE shop_id = ? AND is_active = TRUE",
            (shop_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_first_active_admin() -> Optional[dict]:
    """Tizimdagi birinchi faol adminni olish (fallback uchun)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM admins WHERE is_active = TRUE ORDER BY id ASC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def create_admin(telegram_id: int, full_name: str, 
                       shop_name: str, username: str = None, phone: str = None) -> dict:
    """Yangi admin yaratish"""
    shop_id = str(uuid.uuid4())[:8].upper()  # 8 belgili unikal kod
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO admins (telegram_id, username, full_name, shop_name, shop_id, phone)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
               username = excluded.username,
               full_name = excluded.full_name,
               shop_name = excluded.shop_name,
               phone = COALESCE(excluded.phone, admins.phone),
               is_active = TRUE""",
            (telegram_id, username, full_name, shop_name, shop_id, phone)
        )
        await db.commit()
    # Agar conflict sabab yangilanmagan bo'lsa, mavjud shop_id ni olamiz
    admin = await get_admin_by_telegram_id(telegram_id)
    return {"shop_id": admin["shop_id"], "shop_name": admin["shop_name"]}

async def update_admin_phone(telegram_id: int, phone: str) -> bool:
    """Admin telefon raqamini saqlash"""
    async with aiosqlite.connect(DB_PATH) as db:
        result = await db.execute(
            "UPDATE admins SET phone = ? WHERE telegram_id = ?",
            (phone, telegram_id)
        )
        await db.commit()
        return result.rowcount > 0

# ============================================================
# CUSTOMER QUERIES
# ============================================================

async def add_customer(shop_id: str, full_name: str, phone: str,
                       amount: float, description: str, 
                       due_date: str, notes: str = None) -> dict:
    """Mijoz qo'shish va qarzini yozish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        
        # Mavjud mijozni tekshirish (aynan shu do'konda)
        async with db.execute(
            "SELECT id FROM customers WHERE shop_id = ? AND phone = ?",
            (shop_id, phone)
        ) as cursor:
            existing = await cursor.fetchone()
        
        if existing:
            customer_id = existing["id"]
            # Ismini yoki izohini yangilash (ixtiyoriy)
            await db.execute(
                "UPDATE customers SET full_name = ?, notes = COALESCE(?, notes) WHERE id = ?",
                (full_name, notes, customer_id)
            )
        else:
            # Yangi mijoz yaratish
            cursor = await db.execute(
                """INSERT INTO customers (shop_id, full_name, phone, notes)
                   VALUES (?, ?, ?, ?)""",
                (shop_id, full_name, phone, notes)
            )
            customer_id = cursor.lastrowid
        
        # Qarz qo'shish
        await db.execute(
            """INSERT INTO debts (customer_id, shop_id, amount, description, due_date, status)
               VALUES (?, ?, ?, ?, ?, 'active')""",
            (customer_id, shop_id, amount, description, due_date)
        )
        
        # Mijozning umumiy qarzini yangilash
        await db.execute(
            """UPDATE customers 
               SET total_debt = (SELECT COALESCE(SUM(amount), 0) FROM debts 
                                 WHERE customer_id = ? AND status IN ('active', 'overdue'))
               WHERE id = ?""",
            (customer_id, customer_id)
        )
        await db.commit()
        
        return {"customer_id": customer_id, "is_new": not bool(existing)}

async def get_customers_list(shop_id: str, search: str = None, 
                             status_filter: str = None) -> List[dict]:
    """Admin uchun do'konga tegishli barcha mijozlar ro'yxati"""
    query = """
        SELECT 
            c.id, c.shop_id, c.full_name, c.phone, c.telegram_id,
            c.notes, c.total_debt, c.created_at,
            COUNT(CASE WHEN d.status = 'active' THEN 1 END) as active_debts,
            COUNT(CASE WHEN d.status = 'overdue' THEN 1 END) as overdue_debts,
            MIN(CASE WHEN d.status IN ('active', 'overdue') THEN d.due_date END) as nearest_due
        FROM customers c
        LEFT JOIN debts d ON d.customer_id = c.id
        WHERE c.shop_id = ?
    """
    params: List[Any] = [shop_id]
    
    if search:
        query += " AND (c.full_name LIKE ? OR c.phone LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
        
    query += " GROUP BY c.id"
    
    if status_filter == "overdue":
        query += " HAVING overdue_debts > 0"
    elif status_filter == "active":
        query += " HAVING active_debts > 0"
    elif status_filter == "paid":
        query += " HAVING active_debts = 0 AND overdue_debts = 0"
        
    query += " ORDER BY overdue_debts DESC, nearest_due ASC, c.id DESC"
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_customer_by_id(customer_id: int) -> Optional[dict]:
    """Mijozning to'liq ma'lumoti va unga tegishli do'kon ma'lumotlari"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.*, a.shop_name, a.phone as shop_phone
               FROM customers c
               JOIN admins a ON a.shop_id = c.shop_id
               WHERE c.id = ?""",
            (customer_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_customer_detail(customer_id: int, shop_id: str) -> Optional[dict]:
    """Bir mijozning to'liq ma'lumotlari (faqat belgilangan do'kon uchun)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Mijoz ma'lumotlari
        async with db.execute(
            "SELECT * FROM customers WHERE id = ? AND shop_id = ?",
            (customer_id, shop_id)
        ) as cursor:
            customer = await cursor.fetchone()
        
        if not customer:
            return None
        
        # Qarzlar ro'yxati
        async with db.execute(
            """SELECT * FROM debts 
               WHERE customer_id = ? AND shop_id = ?
               ORDER BY CASE status WHEN 'overdue' THEN 1 WHEN 'active' THEN 2 ELSE 3 END, due_date ASC""",
            (customer_id, shop_id)
        ) as cursor:
            debts = await cursor.fetchall()
        
        return {
            **dict(customer),
            "debts": [dict(d) for d in debts]
        }

async def get_customer_by_phone(phone: str) -> Optional[dict]:
    """Mijozni telefon raqami bo'yicha topish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.*, a.shop_name, a.phone as shop_phone
               FROM customers c
               JOIN admins a ON a.shop_id = c.shop_id
               WHERE c.phone = ?
               ORDER BY c.id DESC LIMIT 1""",
            (phone,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_all_customers_by_phone(phone: str) -> List[dict]:
    """Mijoz bir nechta do'konda bo'lishi mumkinligi uchun barcha yozuvlarni olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.*, a.shop_name, a.phone as shop_phone
               FROM customers c
               JOIN admins a ON a.shop_id = c.shop_id
               WHERE c.phone = ?""",
            (phone,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_customer_by_telegram_id(telegram_id: int) -> List[dict]:
    """Mijozning telegram_id si orqali do'konlardagi yozuvlarini olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.*, a.shop_name, a.phone as shop_phone
               FROM customers c
               JOIN admins a ON a.shop_id = c.shop_id
               WHERE c.telegram_id = ?""",
            (telegram_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def link_customer_telegram(phone: str, telegram_id: int) -> bool:
    """Mijozning Telegram ID sini saqlash"""
    async with aiosqlite.connect(DB_PATH) as db:
        result = await db.execute(
            "UPDATE customers SET telegram_id = ? WHERE phone = ?",
            (telegram_id, phone)
        )
        await db.commit()
        return result.rowcount > 0

# ============================================================
# DEBT QUERIES
# ============================================================

async def mark_debt_paid(debt_id: int, shop_id: str, 
                         admin_id: int, note: str = None) -> bool:
    """Qarzni to'langan deb belgilash"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Qarzni topish va aynan shu shop_id ga tegishliligini tekshirish
        async with db.execute(
            "SELECT id, customer_id, amount FROM debts WHERE id = ? AND shop_id = ?",
            (debt_id, shop_id)
        ) as cursor:
            debt = await cursor.fetchone()
        
        if not debt:
            return False
        
        now = datetime.now().isoformat()
        
        # Qarzni yangilash
        await db.execute(
            """UPDATE debts 
               SET status = 'paid', paid_date = ?, paid_amount = amount, 
                   admin_note = ?, updated_at = ?
               WHERE id = ?""",
            (now, note, now, debt_id)
        )
        
        # To'lov tarixiga yozish
        await db.execute(
            """INSERT INTO payment_history (debt_id, amount, note, admin_id)
               VALUES (?, ?, ?, ?)""",
            (debt_id, debt["amount"], note, admin_id)
        )
        
        # Mijozning umumiy qarzini qayta hisoblash
        await db.execute(
            """UPDATE customers 
               SET total_debt = (SELECT COALESCE(SUM(amount), 0) FROM debts 
                                 WHERE customer_id = ? AND status IN ('active', 'overdue'))
               WHERE id = ?""",
            (debt["customer_id"], debt["customer_id"])
        )
        await db.commit()
        return True

async def update_admin_shop_name(telegram_id: int, shop_name: str) -> bool:
    """Admin do'kon nomini yangilash"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE admins SET shop_name = ? WHERE telegram_id = ?",
            (shop_name.strip(), telegram_id)
        )
        await db.commit()
        return True

async def update_admin_profile(telegram_id: int, full_name: str, shop_name: str, phone: str = None) -> dict:
    """Admin to'liq ma'lumotlarini yangilash yoki yaratish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)) as cur:
            existing = await cur.fetchone()
            
        if existing:
            shop_id = existing["shop_id"]
            await db.execute(
                """UPDATE admins 
                   SET full_name = ?, shop_name = ?, phone = COALESCE(?, phone), is_active = 1
                   WHERE telegram_id = ?""",
                (full_name.strip(), shop_name.strip(), phone, telegram_id)
            )
        else:
            shop_id = str(uuid.uuid4())[:8].upper()
            await db.execute(
                """INSERT INTO admins (telegram_id, full_name, shop_name, shop_id, phone, is_active)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (telegram_id, full_name.strip(), shop_name.strip(), shop_id, phone)
            )
        await db.commit()
        
    return await get_admin_by_telegram_id(telegram_id)

async def get_customer_all_debts(customer_id: int) -> List[dict]:
    """Mijozning barcha qarzlari (faol va to'langan)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT d.*, a.shop_name, a.phone as shop_phone
               FROM debts d
               JOIN admins a ON a.shop_id = d.shop_id
               WHERE d.customer_id = ?
               ORDER BY CASE d.status 
                          WHEN 'overdue' THEN 1 
                          WHEN 'active' THEN 2 
                          ELSE 3 END, 
                        d.due_date ASC""",
            (customer_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_customer_active_debts(customer_id: int) -> List[dict]:
    """Mijozning to'lanmagan qarzlari"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT d.*, a.shop_name, a.phone as shop_phone
               FROM debts d
               JOIN admins a ON a.shop_id = d.shop_id
               WHERE d.customer_id = ? AND d.status != 'paid'
               ORDER BY CASE d.status WHEN 'overdue' THEN 1 ELSE 2 END, d.due_date ASC""",
            (customer_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def update_overdue_statuses() -> int:
    """Muddati o'tgan qarzlarni 'overdue' ga o'tkazish"""
    async with aiosqlite.connect(DB_PATH) as db:
        today = date.today().isoformat()
        result = await db.execute(
            """UPDATE debts 
               SET status = 'overdue', updated_at = CURRENT_TIMESTAMP
               WHERE status = 'active' AND due_date < ?""",
            (today,)
        )
        # Mijozlar umumiy qarzini yangilash
        await db.execute("""
            UPDATE customers 
            SET total_debt = (
                SELECT COALESCE(SUM(d.amount), 0) 
                FROM debts d 
                WHERE d.customer_id = customers.id 
                AND d.status IN ('active', 'overdue')
            )
        """)
        await db.commit()
        return result.rowcount

async def get_debts_for_notification(days_ahead: int) -> List[dict]:
    """Eslatma yuborish kerak bo'lgan qarzlar"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        target_date = (date.today() + timedelta(days=days_ahead)).isoformat()
        
        async with db.execute(
            """SELECT d.id, d.amount, d.due_date, d.description,
                      c.id as customer_id, c.full_name, c.phone, c.telegram_id,
                      a.shop_name, a.phone as admin_phone
               FROM debts d
               JOIN customers c ON c.id = d.customer_id
               JOIN admins a ON a.shop_id = d.shop_id
               WHERE d.due_date = ? 
                 AND d.status = 'active'
                 AND c.telegram_id IS NOT NULL
                 AND d.reminder_sent = FALSE""",
            (target_date,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def mark_reminder_sent(debt_id: int):
    """Eslatma yuborilganligini belgilash"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE debts SET reminder_sent = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (debt_id,)
        )
        await db.commit()

async def log_notification(debt_id: int, customer_id: int, notification_type: str, 
                           success: bool = True, error_message: str = None):
    """Xabarnoma yuborilganini qayd etish"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO notifications_log (debt_id, customer_id, type, success, error_message)
               VALUES (?, ?, ?, ?, ?)""",
            (debt_id, customer_id, notification_type, success, error_message)
        )
        await db.commit()

async def get_admin_stats(shop_id: str) -> dict:
    """Admin statistikasi"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        async with db.execute("""
            SELECT 
                COUNT(DISTINCT c.id) as total_customers,
                COUNT(CASE WHEN d.status = 'active' THEN 1 END) as active_debts,
                COUNT(CASE WHEN d.status = 'overdue' THEN 1 END) as overdue_debts,
                COALESCE(SUM(CASE WHEN d.status IN ('active', 'overdue') THEN d.amount END), 0) as total_debt_sum,
                COALESCE(SUM(CASE WHEN d.status = 'paid' AND d.paid_date >= DATE('now', '-30 days') 
                             THEN d.paid_amount END), 0) as month_paid_sum,
                COUNT(CASE WHEN d.due_date BETWEEN DATE('now') AND DATE('now', '+7 days') 
                           AND d.status = 'active' THEN 1 END) as due_this_week
            FROM customers c
            LEFT JOIN debts d ON d.customer_id = c.id
            WHERE c.shop_id = ?
        """, (shop_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {
                "total_customers": 0,
                "active_debts": 0,
                "overdue_debts": 0,
                "total_debt_sum": 0,
                "month_paid_sum": 0,
                "due_this_week": 0
            }

async def delete_debt(debt_id: int, shop_id: str) -> bool:
    """Qarzni o'chirish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT customer_id FROM debts WHERE id = ? AND shop_id = ?", (debt_id, shop_id)) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        customer_id = row["customer_id"]
        
        await db.execute("DELETE FROM debts WHERE id = ? AND shop_id = ?", (debt_id, shop_id))
        await db.execute(
            """UPDATE customers 
               SET total_debt = (SELECT COALESCE(SUM(amount), 0) FROM debts 
                                 WHERE customer_id = ? AND status IN ('active', 'overdue'))
               WHERE id = ?""",
            (customer_id, customer_id)
        )
        await db.commit()
        return True

async def update_admin_shop_name(telegram_id: int, shop_name: str) -> bool:
    """Admin do'kon nomini yangilash"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE admins SET shop_name = ? WHERE telegram_id = ?",
            (shop_name.strip(), telegram_id)
        )
        await db.commit()
        return True

async def update_admin_profile(telegram_id: int, full_name: str, shop_name: str, phone: str = None) -> dict:
    """Admin to'liq ma'lumotlarini yangilash yoki yaratish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)) as cur:
            existing = await cur.fetchone()
            
        if existing:
            shop_id = existing["shop_id"]
            await db.execute(
                """UPDATE admins 
                   SET full_name = ?, shop_name = ?, phone = COALESCE(?, phone), is_active = 1
                   WHERE telegram_id = ?""",
                (full_name.strip(), shop_name.strip(), phone, telegram_id)
            )
        else:
            shop_id = str(uuid.uuid4())[:8].upper()
            await db.execute(
                """INSERT INTO admins (telegram_id, full_name, shop_name, shop_id, phone, is_active)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (telegram_id, full_name.strip(), shop_name.strip(), shop_id, phone)
            )
        await db.commit()
        
    return await get_admin_by_telegram_id(telegram_id)

async def get_customer_all_debts(customer_id: int) -> List[dict]:
    """Mijozning barcha qarzlari (faol va to'langan)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT d.*, a.shop_name, a.phone as shop_phone
               FROM debts d
               JOIN admins a ON a.shop_id = d.shop_id
               WHERE d.customer_id = ?
               ORDER BY CASE d.status 
                          WHEN 'overdue' THEN 1 
                          WHEN 'active' THEN 2 
                          ELSE 3 END, 
                        d.due_date ASC""",
            (customer_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


