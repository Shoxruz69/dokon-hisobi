import uuid
import logging
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

from database.db import (
    db_fetch_one,
    db_fetch_all,
    db_execute,
    db_execute_insert,
    is_postgres
)

logger = logging.getLogger(__name__)

# ============================================================
# 1. ADMIN SO'ROVLARI
# ============================================================

async def get_admin_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Adminni telegram_id bo'yicha olish"""
    return await db_fetch_one(
        "SELECT * FROM admins WHERE telegram_id = ? AND is_active = TRUE",
        telegram_id
    )

async def get_admin_by_shop_id(shop_id: str) -> Optional[dict]:
    """Adminni shop_id bo'yicha olish"""
    return await db_fetch_one(
        "SELECT * FROM admins WHERE shop_id = ? AND is_active = TRUE",
        shop_id
    )

async def get_first_active_admin() -> Optional[dict]:
    """Tizimdagi birinchi faol adminni olish (fallback)"""
    return await db_fetch_one(
        "SELECT * FROM admins WHERE is_active = TRUE ORDER BY id ASC LIMIT 1"
    )

async def create_admin(telegram_id: int, full_name: str, 
                       shop_name: str, username: str = None, phone: str = None) -> dict:
    """Yangi admin yaratish"""
    shop_id = str(uuid.uuid4())[:8].upper()
    await db_execute("""
        INSERT INTO admins (telegram_id, username, full_name, shop_name, shop_id, phone, is_active)
        VALUES (?, ?, ?, ?, ?, ?, TRUE)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username = EXCLUDED.username,
            full_name = EXCLUDED.full_name,
            shop_name = EXCLUDED.shop_name,
            phone = COALESCE(EXCLUDED.phone, admins.phone),
            is_active = TRUE
    """, telegram_id, username, full_name.strip(), shop_name.strip(), shop_id, phone)
    
    return await get_admin_by_telegram_id(telegram_id)

async def update_admin_shop_name(telegram_id: int, shop_name: str) -> bool:
    """Admin do'kon nomini yangilash"""
    await db_execute(
        "UPDATE admins SET shop_name = ? WHERE telegram_id = ?",
        shop_name.strip(), telegram_id
    )
    return True

async def update_admin_profile(telegram_id: int, full_name: str, shop_name: str, phone: str = None) -> dict:
    """Admin to'liq ma'lumotlarini yangilash yoki yaratish"""
    existing = await db_fetch_one("SELECT * FROM admins WHERE telegram_id = ?", telegram_id)
    if existing:
        await db_execute("""
            UPDATE admins 
            SET full_name = ?, shop_name = ?, phone = COALESCE(?, phone), is_active = TRUE
            WHERE telegram_id = ?
        """, full_name.strip(), shop_name.strip(), phone, telegram_id)
    else:
        shop_id = str(uuid.uuid4())[:8].upper()
        await db_execute("""
            INSERT INTO admins (telegram_id, full_name, shop_name, shop_id, phone, is_active)
            VALUES (?, ?, ?, ?, ?, TRUE)
        """, telegram_id, full_name.strip(), shop_name.strip(), shop_id, phone)
        
    return await get_admin_by_telegram_id(telegram_id)

async def update_admin_phone(telegram_id: int, phone: str) -> bool:
    """Admin telefon raqamini yangilash"""
    await db_execute("UPDATE admins SET phone = ? WHERE telegram_id = ?", phone, telegram_id)
    return True

# ============================================================
# 2. MIJOZ VA QARZ QO'SHISH
# ============================================================

async def add_customer(
    shop_id: str,
    full_name: str,
    phone: str,
    amount: float,
    description: str,
    due_date: str,
    telegram_id: Optional[int] = None,
    notes: Optional[str] = None,
    debt_date: Optional[str] = None
) -> dict:
    """Mijoz va uning dastlabki qarzini kiritish"""
    d_date = date.fromisoformat(debt_date) if debt_date else date.today()
    d_due = date.fromisoformat(due_date) if isinstance(due_date, str) else due_date

    # 1. Mijoz bor-yo'qligini tekshirish
    customer = await db_fetch_one(
        "SELECT id, total_debt FROM customers WHERE shop_id = ? AND phone = ?",
        shop_id, phone
    )
    
    is_new = False
    if not customer:
        customer_id = await db_execute_insert("""
            INSERT INTO customers (shop_id, full_name, phone, telegram_id, notes, total_debt)
            VALUES (?, ?, ?, ?, ?, 0)
        """, shop_id, full_name.strip(), phone.strip(), telegram_id, notes)
        is_new = True
    else:
        customer_id = customer["id"]
        if telegram_id:
            await db_execute("UPDATE customers SET telegram_id = ? WHERE id = ?", telegram_id, customer_id)

    # 2. Qarzni kiritish
    debt_id = await db_execute_insert("""
        INSERT INTO debts (customer_id, shop_id, amount, description, debt_date, due_date, status)
        VALUES (?, ?, ?, ?, ?, ?, 'active')
    """, customer_id, shop_id, float(amount), description.strip(), d_date, d_due)

    # 3. Jami qarzni qayta hisoblash
    total_row = await db_fetch_one(
        "SELECT COALESCE(SUM(amount), 0) as total FROM debts WHERE customer_id = ? AND status IN ('active', 'overdue')",
        customer_id
    )
    new_total = float(total_row["total"]) if total_row else float(amount)
    await db_execute("UPDATE customers SET total_debt = ? WHERE id = ?", new_total, customer_id)

    return {
        "customer_id": customer_id,
        "debt_id": debt_id,
        "is_new": is_new,
        "total_debt": new_total
    }

# ============================================================
# 3. MIJOZLARNI OLISH VA QIDIRISH
# ============================================================

async def get_customers_list(shop_id: str, search: Optional[str] = None, 
                             status_filter: str = "all") -> List[dict]:
    """Do'konning barcha mijozlarini qidiruv bilan olish"""
    query = """
        SELECT c.*,
            COUNT(CASE WHEN d.status = 'active' THEN 1 END) as active_debts,
            COUNT(CASE WHEN d.status = 'overdue' THEN 1 END) as overdue_debts,
            MIN(CASE WHEN d.status IN ('active', 'overdue') THEN d.due_date END) as nearest_due
        FROM customers c
        LEFT JOIN debts d ON d.customer_id = c.id
        WHERE c.shop_id = ?
    """
    params = [shop_id]

    if search:
        search_pattern = f"%{search.strip()}%"
        query += " AND (c.full_name ILIKE ? OR c.phone ILIKE ?)" if is_postgres() else " AND (c.full_name LIKE ? OR c.phone LIKE ?)"
        params.extend([search_pattern, search_pattern])

    query += " GROUP BY c.id"

    if status_filter == "overdue":
        query += " HAVING COUNT(CASE WHEN d.status = 'overdue' THEN 1 END) > 0"
    elif status_filter == "active":
        query += " HAVING COUNT(CASE WHEN d.status = 'active' THEN 1 END) > 0"
    elif status_filter == "paid":
        query += " HAVING c.total_debt = 0"

    query += " ORDER BY c.total_debt DESC, c.full_name ASC"

    return await db_fetch_all(query, *params)

async def get_customer_by_id(customer_id: int) -> Optional[dict]:
    """Mijozning to'liq ma'lumoti va do'koni"""
    return await db_fetch_one("""
        SELECT c.*, a.shop_name, a.phone as shop_phone
        FROM customers c
        JOIN admins a ON a.shop_id = c.shop_id
        WHERE c.id = ?
    """, customer_id)

async def get_customer_detail(customer_id: int, shop_id: Optional[str] = None) -> Optional[dict]:
    """Bir mijozning to'liq kartochkasi va qarzlari"""
    if shop_id:
        cust = await db_fetch_one("SELECT * FROM customers WHERE id = ? AND shop_id = ?", customer_id, shop_id)
    else:
        cust = await db_fetch_one("SELECT * FROM customers WHERE id = ?", customer_id)
        
    if not cust:
        return None
        
    debts = await get_customer_all_debts(customer_id)
    cust_dict = dict(cust)
    cust_dict["debts"] = debts
    return cust_dict

async def get_customer_by_phone(shop_id: str, phone: str) -> Optional[dict]:
    """Telefon raqami bo'yicha mijozni qidirish"""
    return await db_fetch_one("SELECT * FROM customers WHERE shop_id = ? AND phone = ?", shop_id, phone)

async def get_all_customers_by_phone(phone: str) -> List[dict]:
    """Barcha do'konlardan telefon raqami bo'yicha mijozlarni topish"""
    return await db_fetch_all("""
        SELECT c.*, a.shop_name, a.phone as shop_phone
        FROM customers c
        JOIN admins a ON a.shop_id = c.shop_id
        WHERE c.phone = ?
    """, phone)

async def get_customer_by_telegram_id(telegram_id: int) -> List[dict]:
    """Mijozning telegram_id si orqali olish"""
    return await db_fetch_all("""
        SELECT c.*, a.shop_name, a.phone as shop_phone
        FROM customers c
        JOIN admins a ON a.shop_id = c.shop_id
        WHERE c.telegram_id = ?
    """, telegram_id)

async def link_customer_telegram(phone: str, telegram_id: int) -> bool:
    """Mijozning telefon raqamiga uning Telegram ID sini bog'lash"""
    await db_execute("UPDATE customers SET telegram_id = ? WHERE phone = ?", telegram_id, phone)
    return True

# ============================================================
# 4. QARZNI TO'LASH VA BOG'LIQ AMALLAR
# ============================================================

async def mark_debt_paid(debt_id: int, shop_id: Optional[str] = None, 
                         admin_id: int = 0, note: Optional[str] = None) -> bool:
    """Qarzni to'langan deb belgilash"""
    if shop_id:
        debt = await db_fetch_one("SELECT id, customer_id, amount FROM debts WHERE id = ? AND shop_id = ?", debt_id, shop_id)
    else:
        debt = await db_fetch_one("SELECT id, customer_id, amount FROM debts WHERE id = ?", debt_id)

    if not debt:
        return False

    customer_id = debt["customer_id"]
    amount = float(debt["amount"])
    now_dt = datetime.now()

    # 1. Qarzni paid ga o'tkazish
    await db_execute("""
        UPDATE debts 
        SET status = 'paid', paid_date = ?, paid_amount = ?, admin_note = ?, updated_at = ?
        WHERE id = ?
    """, now_dt, amount, note, now_dt, debt_id)

    # 2. To'lovlar tarixiga qo'shish
    await db_execute_insert("""
        INSERT INTO payment_history (debt_id, amount, paid_at, note, admin_id)
        VALUES (?, ?, ?, ?, ?)
    """, debt_id, amount, now_dt, note, admin_id)

    # 3. Mijozning jami qarzini yangilash
    total_row = await db_fetch_one(
        "SELECT COALESCE(SUM(amount), 0) as total FROM debts WHERE customer_id = ? AND status IN ('active', 'overdue')",
        customer_id
    )
    new_total = float(total_row["total"]) if total_row else 0.0
    await db_execute("UPDATE customers SET total_debt = ? WHERE id = ?", new_total, customer_id)

    return True

async def get_customer_all_debts(customer_id: int) -> List[dict]:
    """Mijozning barcha qarzlari (faol va to'langan)"""
    return await db_fetch_all("""
        SELECT d.*, a.shop_name, a.phone as shop_phone
        FROM debts d
        JOIN admins a ON a.shop_id = d.shop_id
        WHERE d.customer_id = ?
        ORDER BY CASE d.status 
                   WHEN 'overdue' THEN 1 
                   WHEN 'active' THEN 2 
                   ELSE 3 END, 
                 d.due_date ASC
    """, customer_id)

async def get_customer_active_debts(customer_id: int) -> List[dict]:
    """Mijozning to'lanmagan qarzlari"""
    return await db_fetch_all("""
        SELECT d.*, a.shop_name, a.phone as shop_phone
        FROM debts d
        JOIN admins a ON a.shop_id = d.shop_id
        WHERE d.customer_id = ? AND d.status != 'paid'
        ORDER BY CASE d.status WHEN 'overdue' THEN 1 ELSE 2 END, d.due_date ASC
    """, customer_id)

async def update_overdue_statuses() -> int:
    """Muddati o'tgan qarzlarni avtomatik overdue holatiga o'tkazish"""
    res = await db_execute("""
        UPDATE debts 
        SET status = 'overdue', updated_at = CURRENT_TIMESTAMP
        WHERE due_date < CURRENT_DATE AND status = 'active'
    """)
    return 1

async def get_debts_for_notification(days_ahead: int) -> List[dict]:
    """Eslatma yuborish kerak bo'lgan qarzlar"""
    target_date = date.today() + timedelta(days=days_ahead)
    return await db_fetch_all("""
        SELECT d.id, d.amount, d.due_date, d.description,
               c.id as customer_id, c.full_name, c.phone, c.telegram_id,
               a.shop_name, a.phone as admin_phone
        FROM debts d
        JOIN customers c ON c.id = d.customer_id
        JOIN admins a ON a.shop_id = d.shop_id
        WHERE d.due_date = ? 
          AND d.status = 'active'
          AND c.telegram_id IS NOT NULL
          AND d.reminder_sent = FALSE
    """, target_date)

async def mark_reminder_sent(debt_id: int):
    """Eslatma yuborilganligini belgilash"""
    await db_execute("UPDATE debts SET reminder_sent = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = ?", debt_id)

async def log_notification(debt_id: int, customer_id: int, ntype: str, 
                           success: bool, error_msg: Optional[str] = None):
    """Xabarnoma logini yozish"""
    await db_execute_insert("""
        INSERT INTO notifications_log (debt_id, customer_id, type, success, error_message)
        VALUES (?, ?, ?, ?, ?)
    """, debt_id, customer_id, ntype, success, error_msg)

# ============================================================
# 5. STATISTIKA VA O'CHIRISH
# ============================================================

async def get_admin_stats(shop_id: str) -> dict:
    """Admin boshqaruv paneli uchun umumiy statistika"""
    row = await db_fetch_one("""
        SELECT 
            COUNT(DISTINCT c.id) as total_customers,
            COUNT(DISTINCT CASE WHEN d.status = 'active' THEN d.id END) as active_debts,
            COUNT(DISTINCT CASE WHEN d.status = 'overdue' THEN d.id END) as overdue_debts,
            COALESCE(SUM(CASE WHEN d.status IN ('active', 'overdue') THEN d.amount END), 0) as total_debt_sum,
            COALESCE(SUM(CASE WHEN d.status = 'paid' AND d.paid_date >= DATE('now', '-30 days') 
                         THEN d.paid_amount END), 0) as month_paid_sum,
            COUNT(DISTINCT CASE WHEN d.due_date BETWEEN DATE('now') AND DATE('now', '+7 days') 
                       AND d.status = 'active' THEN d.id END) as due_this_week
        FROM customers c
        LEFT JOIN debts d ON d.customer_id = c.id
        WHERE c.shop_id = ?
    """, shop_id)
    
    admin = await get_admin_by_shop_id(shop_id)
    shop_name = admin["shop_name"] if admin else "Do'kon"
    
    stats = dict(row) if row else {
        "total_customers": 0,
        "active_debts": 0,
        "overdue_debts": 0,
        "total_debt_sum": 0,
        "month_paid_sum": 0,
        "due_this_week": 0
    }
    stats["shop_name"] = shop_name
    stats["shop_id"] = shop_id
    return stats

async def delete_debt(debt_id: int, shop_id: str) -> bool:
    """Qarzni o'chirish"""
    row = await db_fetch_one("SELECT customer_id FROM debts WHERE id = ? AND shop_id = ?", debt_id, shop_id)
    if not row:
        return False
    customer_id = row["customer_id"]
    
    await db_execute("DELETE FROM debts WHERE id = ? AND shop_id = ?", debt_id, shop_id)
    total_row = await db_fetch_one(
        "SELECT COALESCE(SUM(amount), 0) as total FROM debts WHERE customer_id = ? AND status IN ('active', 'overdue')",
        customer_id
    )
    new_total = float(total_row["total"]) if total_row else 0.0
    await db_execute("UPDATE customers SET total_debt = ? WHERE id = ?", new_total, customer_id)
    return True
