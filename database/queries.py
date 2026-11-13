import uuid
import logging
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

from database.db import (
    db_fetch_one,
    db_fetch_all,
    db_execute,
    db_execute_insert,
    is_postgres
)

from config import settings

logger = logging.getLogger(__name__)

# ============================================================
# ADMIN NOMI / LABELINI ANIQLASH
# ============================================================
def resolve_admin_label(admin_id: Optional[int], custom_name: Optional[str] = None) -> str:
    """Admin ID si yoki ismini chiroyli qilib qaytarish"""
    known = {
        264625389: "Rustamjon",
        6715367177: "Abdulhamid"
    }
    try:
        aid = int(admin_id) if admin_id else None
    except Exception:
        aid = None

    if aid and aid in known:
        return known[aid]

    if custom_name and custom_name.strip() and custom_name.strip() not in ("None", "Admin", "null", ""):
        return custom_name.strip()

    if aid:
        return known.get(aid, "Rustamjon")
    return "Rustamjon"

# ============================================================
# 1. ADMIN SO'ROVLARI
# ============================================================

async def get_admin_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Adminni telegram_id bo'yicha olish"""
    admin = await db_fetch_one(
        "SELECT * FROM admins WHERE telegram_id = ? AND is_active = TRUE",
        telegram_id
    )
    if admin:
        admin["full_name"] = resolve_admin_label(telegram_id, admin.get("full_name"))
        return admin

    # Agar bazada bu telegram_id bo'lmasa, lekin settings.is_admin_id() bo'lsa
    if settings.is_admin_id(telegram_id):
        first = await get_first_active_admin()
        if first:
            res = dict(first)
            res["telegram_id"] = telegram_id
            res["full_name"] = resolve_admin_label(telegram_id)
            return res
            
    return None

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
    phone: Optional[str],
    amount: float,
    description: Optional[str],
    due_date: str,
    telegram_id: Optional[int] = None,
    notes: Optional[str] = None,
    debt_date: Optional[str] = None,
    admin_id: Optional[int] = None,
    admin_name: Optional[str] = None
) -> dict:
    """Mijoz va uning dastlabki qarzini kiritish"""
    d_date = date.fromisoformat(debt_date) if debt_date else date.today()
    d_due = date.fromisoformat(due_date) if isinstance(due_date, str) else due_date
    resolved_name = resolve_admin_label(admin_id, admin_name)

    clean_phone = phone.strip() if phone and str(phone).strip() else None
    desc_val = description.strip() if description and str(description).strip() else "Nasiya savdo"

    # 1. Mijoz bor-yo'qligini tekshirish
    customer = None
    if clean_phone:
        customer = await db_fetch_one(
            "SELECT id, total_debt FROM customers WHERE shop_id = ? AND phone = ?",
            shop_id, clean_phone
        )
    else:
        customer = await db_fetch_one(
            "SELECT id, total_debt FROM customers WHERE shop_id = ? AND full_name = ? AND (phone IS NULL OR phone = '')",
            shop_id, full_name.strip()
        )
    
    is_new = False
    if not customer:
        customer_id = await db_execute_insert("""
            INSERT INTO customers (shop_id, full_name, phone, telegram_id, notes, total_debt)
            VALUES (?, ?, ?, ?, ?, 0)
        """, shop_id, full_name.strip(), clean_phone, telegram_id, notes)
        is_new = True
    else:
        customer_id = customer["id"]
        if telegram_id:
            await db_execute("UPDATE customers SET telegram_id = ? WHERE id = ?", telegram_id, customer_id)

    # 2. Qarzni kiritish (qaysi admin qo'shgani bilan)
    debt_id = await db_execute_insert("""
        INSERT INTO debts (customer_id, shop_id, amount, description, debt_date, due_date, status, created_by_admin_id, created_by_admin_name)
        VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
    """, customer_id, shop_id, float(amount), desc_val, d_date, d_due, admin_id, resolved_name)

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
        "total_debt": new_total,
        "created_by_admin_name": resolved_name
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

    query += " ORDER BY c.id DESC"

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
    """Bir mijozning to'liq kartochkasi, qarzlari va to'lovlari"""
    if shop_id:
        cust = await db_fetch_one("SELECT * FROM customers WHERE id = ? AND shop_id = ?", customer_id, shop_id)
    else:
        cust = await db_fetch_one("SELECT * FROM customers WHERE id = ?", customer_id)
        
    if not cust:
        return None
        
    debts = await get_customer_all_debts(customer_id)
    payments = await get_customer_payments(customer_id)
    cust_dict = dict(cust)
    cust_dict["debts"] = debts
    cust_dict["payments"] = payments
    return cust_dict

async def get_customer_payments(customer_id: int) -> List[dict]:
    """Mijozning to'lovlar tarixi"""
    return await db_fetch_all("""
        SELECT ph.id, ph.debt_id, ph.amount, ph.paid_at, ph.note, ph.admin_id, ph.admin_name,
               d.description as debt_description
        FROM payment_history ph
        JOIN debts d ON d.id = ph.debt_id
        WHERE d.customer_id = ?
        ORDER BY ph.paid_at DESC
    """, customer_id)

async def update_customer(
    customer_id: int,
    shop_id: str,
    full_name: str,
    phone: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[dict]:
    """Mijoz ma'lumotlarini (ism, telefon, izoh) yangilash"""
    clean_name = full_name.strip()
    clean_phone = phone.strip() if phone and str(phone).strip() else None
    clean_notes = notes.strip() if notes and str(notes).strip() else None

    # Do'konga tegishli ekanini tekshirish
    cust = await db_fetch_one("SELECT * FROM customers WHERE id = ? AND shop_id = ?", customer_id, shop_id)
    if not cust:
        return None

    # Agar telefon kiritilgan bo'lsa, boshqa mijozda bu telefon yo'qligini tekshirish
    if clean_phone:
        existing = await db_fetch_one(
            "SELECT id FROM customers WHERE shop_id = ? AND phone = ? AND id != ?",
            shop_id, clean_phone, customer_id
        )
        if existing:
            raise ValueError(f"Ushbu telefon raqami ({clean_phone}) boshqa mijozda mavjud")

    await db_execute("""
        UPDATE customers 
        SET full_name = ?, phone = ?, notes = ?
        WHERE id = ? AND shop_id = ?
    """, clean_name, clean_phone, clean_notes, customer_id, shop_id)

    return await db_fetch_one("SELECT * FROM customers WHERE id = ?", customer_id)

async def delete_customer(customer_id: int, shop_id: str) -> bool:
    """Mijozni va uning barcha bog'liq qarz/to'lov ma'lumotlarini to'liq o'chirish"""
    cust = await db_fetch_one("SELECT * FROM customers WHERE id = ? AND shop_id = ?", customer_id, shop_id)
    if not cust:
        return False

    # 1. To'lovlar tarixini o'chirish
    await db_execute("""
        DELETE FROM payment_history 
        WHERE debt_id IN (SELECT id FROM debts WHERE customer_id = ?)
    """, customer_id)

    # 2. Xabarnomalar tarixini o'chirish
    await db_execute("DELETE FROM notifications_log WHERE customer_id = ?", customer_id)

    # 3. Qarzlarni o'chirish
    await db_execute("DELETE FROM debts WHERE customer_id = ? AND shop_id = ?", customer_id, shop_id)

    # 4. Mijozning o'zini o'chirish
    await db_execute("DELETE FROM customers WHERE id = ? AND shop_id = ?", customer_id, shop_id)

    return True

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
                         admin_id: int = 0, note: Optional[str] = None,
                         admin_name: Optional[str] = None) -> Optional[dict]:
    """Qarzni to'langan deb belgilash"""
    if shop_id:
        debt = await db_fetch_one("SELECT * FROM debts WHERE id = ? AND shop_id = ?", debt_id, shop_id)
    else:
        debt = await db_fetch_one("SELECT * FROM debts WHERE id = ?", debt_id)

    if not debt:
        return None

    customer_id = debt["customer_id"]
    amount = float(debt["amount"])
    now_dt = datetime.now()
    resolved_name = resolve_admin_label(admin_id, admin_name)

    # 1. Qarzni paid ga o'tkazish
    await db_execute("""
        UPDATE debts 
        SET status = 'paid', paid_date = ?, paid_amount = ?, admin_note = ?, updated_at = ?
        WHERE id = ?
    """, now_dt, amount, note, now_dt, debt_id)

    # 2. To'lovlar tarixiga qo'shish (admin nomi bilan)
    await db_execute_insert("""
        INSERT INTO payment_history (debt_id, amount, paid_at, note, admin_id, admin_name)
        VALUES (?, ?, ?, ?, ?, ?)
    """, debt_id, amount, now_dt, note, admin_id, resolved_name)

    # 3. Mijozning jami qarzini yangilash
    total_row = await db_fetch_one(
        "SELECT COALESCE(SUM(amount), 0) as total FROM debts WHERE customer_id = ? AND status IN ('active', 'overdue')",
        customer_id
    )
    new_total = float(total_row["total"]) if total_row else 0.0
    await db_execute("UPDATE customers SET total_debt = ? WHERE id = ?", new_total, customer_id)

    cust = await db_fetch_one("SELECT * FROM customers WHERE id = ?", customer_id)
    admin = await get_admin_by_shop_id(debt["shop_id"])

    return {
        "success": True,
        "debt": debt,
        "customer": cust,
        "shop_name": admin["shop_name"] if admin else "Do'kon",
        "paid_amount": amount,
        "remaining_debt": new_total,
        "admin_name": resolved_name
    }

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
    try:
        await db_execute_insert("""
            INSERT INTO notifications_log (debt_id, customer_id, type, success, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, debt_id, customer_id, ntype, success, error_msg)
    except Exception as e:
        logger.warning(f"log_notification yozishda ogohlantirish: {e}")

async def get_all_customers_with_active_debts() -> List[dict]:
    """Qarzi bor barcha mijozlar va ularning faol/kechikkan qarzlari ro'yxati (19:00 xabarlari uchun)"""
    rows = await db_fetch_all("""
        SELECT 
            c.id as customer_id,
            c.full_name,
            c.phone,
            c.telegram_id,
            c.total_debt,
            c.shop_id,
            a.shop_name,
            a.phone as admin_phone,
            d.id as debt_id,
            d.amount as debt_amount,
            d.description as debt_description,
            d.due_date,
            d.status as debt_status,
            d.debt_date
        FROM customers c
        JOIN debts d ON d.customer_id = c.id AND d.status IN ('active', 'overdue')
        LEFT JOIN admins a ON a.shop_id = c.shop_id
        ORDER BY c.id, d.due_date ASC
    """)
    
    customers_map: Dict[int, dict] = {}
    for r in rows:
        cid = r["customer_id"]
        if cid not in customers_map:
            customers_map[cid] = {
                "customer_id": cid,
                "full_name": r["full_name"],
                "phone": r["phone"],
                "telegram_id": r["telegram_id"],
                "total_debt": float(r["total_debt"] or 0),
                "shop_id": r["shop_id"],
                "shop_name": r["shop_name"] or "Do'kon",
                "admin_phone": r["admin_phone"],
                "debts": []
            }
        customers_map[cid]["debts"].append({
            "debt_id": r["debt_id"],
            "amount": float(r["debt_amount"] or 0),
            "description": r["debt_description"],
            "due_date": r["due_date"],
            "status": r["debt_status"],
            "debt_date": r["debt_date"]
        })
        
    # Haqiqiy qarz summasini hisoblash va faqat qarzi borlarni qoldirish
    result = []
    for cust in customers_map.values():
        calc_sum = sum(d["amount"] for d in cust["debts"])
        cust["total_debt"] = max(cust["total_debt"], calc_sum)
        if cust["total_debt"] > 0 and cust["debts"]:
            result.append(cust)
            
    return result

# ============================================================
# 5. STATISTIKA VA O'CHIRISH
# ============================================================

async def get_admin_stats(shop_id: str, target_date: Optional[str] = None) -> dict:
    """Admin boshqaruv paneli uchun batafsil statistika"""
    return await get_detailed_stats(shop_id, target_date)

async def get_detailed_stats(shop_id: str, target_date: Optional[str] = None) -> dict:
    """Kunlik (bugun yoki tanlangan sana), oylik va umumiy savdo/qarz statistikasi"""
    today_dt = date.today()
    if not target_date or target_date == "today":
        t_date = today_dt
    else:
        try:
            t_date = date.fromisoformat(target_date)
        except Exception:
            t_date = today_dt

    month_start = t_date.replace(day=1)

    # Barcha statistik so'rovlarni PARALLEL ravishda yuborish (bir necha barobar tezkor)
    (
        given_list,
        paid_list,
        month_given,
        month_paid,
        overall_row,
        admin
    ) = await asyncio.gather(
        # 1. Tanlangan kungi berilgan qarzlar ro'yxati
        db_fetch_all("""
            SELECT d.id, d.customer_id, d.amount, d.description, d.due_date, d.created_at,
                   d.created_by_admin_id, d.created_by_admin_name,
                   c.full_name as customer_name, c.phone as customer_phone
            FROM debts d
            JOIN customers c ON c.id = d.customer_id
            WHERE d.shop_id = ? AND d.debt_date = ?
            ORDER BY d.id DESC
        """, shop_id, t_date),
        # 2. Tanlangan kungi undirilgan to'lovlar ro'yxati
        db_fetch_all("""
            SELECT ph.id, ph.debt_id, ph.amount, ph.paid_at, ph.note, ph.admin_id, ph.admin_name,
                   d.customer_id, d.description as debt_description,
                   c.full_name as customer_name, c.phone as customer_phone
            FROM payment_history ph
            JOIN debts d ON d.id = ph.debt_id
            JOIN customers c ON c.id = d.customer_id
            WHERE d.shop_id = ? AND DATE(ph.paid_at) = ?
            ORDER BY ph.id DESC
        """, shop_id, t_date),
        # 3. Oylik berilgan qarzlar
        db_fetch_one("""
            SELECT 
                COUNT(DISTINCT customer_id) as cust_count,
                COUNT(id) as debt_count,
                COALESCE(SUM(amount), 0) as total_sum
            FROM debts 
            WHERE shop_id = ? AND debt_date >= ?
        """, shop_id, month_start),
        # 4. Oylik undirilgan to'lovlar
        db_fetch_one("""
            SELECT 
                COUNT(DISTINCT d.customer_id) as cust_count,
                COUNT(ph.id) as pay_count,
                COALESCE(SUM(ph.amount), 0) as total_sum
            FROM payment_history ph
            JOIN debts d ON d.id = ph.debt_id
            WHERE d.shop_id = ? AND DATE(ph.paid_at) >= ?
        """, shop_id, month_start),
        # 5. Umumiy ko'rsatkichlar
        db_fetch_one("""
            SELECT 
                COUNT(DISTINCT c.id) as total_customers,
                COUNT(DISTINCT CASE WHEN d.status = 'active' THEN d.id END) as active_debts,
                COUNT(DISTINCT CASE WHEN d.status = 'overdue' THEN d.id END) as overdue_debts,
                COALESCE(SUM(CASE WHEN d.status IN ('active', 'overdue') THEN d.amount END), 0) as total_debt_sum,
                COUNT(DISTINCT CASE WHEN d.due_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days') 
                           AND d.status = 'active' THEN d.id END) as due_this_week
            FROM customers c
            LEFT JOIN debts d ON d.customer_id = c.id
            WHERE c.shop_id = ?
        """, shop_id),
        # 6. Do'kon ma'lumotlari
        get_admin_by_shop_id(shop_id)
    )

    given_row = {
        "cust_count": len(set(d["customer_id"] for d in (given_list or []))),
        "debt_count": len(given_list or []),
        "total_sum": sum(float(d.get("amount") or 0) for d in (given_list or []))
    }
    paid_row = {
        "cust_count": len(set(p["customer_id"] for p in (paid_list or []))),
        "pay_count": len(paid_list or []),
        "total_sum": sum(float(p.get("amount") or 0) for p in (paid_list or []))
    }

    shop_name = admin["shop_name"] if admin else "Do'kon"

    return {
        "shop_id": shop_id,
        "shop_name": shop_name,
        "selected_date": str(t_date),
        "is_today": (t_date == today_dt),
        "daily": {
            "date": str(t_date),
            "given_customers_count": int(given_row["cust_count"]) if given_row else 0,
            "given_debts_count": int(given_row["debt_count"]) if given_row else 0,
            "given_total_sum": float(given_row["total_sum"]) if given_row else 0.0,
            "collected_customers_count": int(paid_row["cust_count"]) if paid_row else 0,
            "collected_payments_count": int(paid_row["pay_count"]) if paid_row else 0,
            "collected_total_sum": float(paid_row["total_sum"]) if paid_row else 0.0,
            "net_flow": (float(paid_row["total_sum"]) if paid_row else 0.0) - (float(given_row["total_sum"]) if given_row else 0.0),
            "given_list": given_list,
            "paid_list": paid_list
        },
        "monthly": {
            "month_start": str(month_start),
            "given_customers_count": int(month_given["cust_count"]) if month_given else 0,
            "given_debts_count": int(month_given["debt_count"]) if month_given else 0,
            "given_total_sum": float(month_given["total_sum"]) if month_given else 0.0,
            "collected_customers_count": int(month_paid["cust_count"]) if month_paid else 0,
            "collected_payments_count": int(month_paid["pay_count"]) if month_paid else 0,
            "collected_total_sum": float(month_paid["total_sum"]) if month_paid else 0.0,
            "net_flow": (float(month_paid["total_sum"]) if month_paid else 0.0) - (float(month_given["total_sum"]) if month_given else 0.0)
        },
        "overall": {
            "total_debt_sum": float(overall_row["total_debt_sum"]) if overall_row else 0.0,
            "total_customers": int(overall_row["total_customers"]) if overall_row else 0,
            "active_debts": int(overall_row["active_debts"]) if overall_row else 0,
            "overdue_debts": int(overall_row["overdue_debts"]) if overall_row else 0,
            "due_this_week": int(overall_row["due_this_week"]) if overall_row else 0
        },
        # Dashboard asosiy kartalari uchun moslik
        "total_customers": int(overall_row["total_customers"]) if overall_row else 0,
        "active_debts": int(overall_row["active_debts"]) if overall_row else 0,
        "overdue_debts": int(overall_row["overdue_debts"]) if overall_row else 0,
        "total_debt_sum": float(overall_row["total_debt_sum"]) if overall_row else 0.0,
        "month_paid_sum": float(month_paid["total_sum"]) if month_paid else 0.0,
        "due_this_week": int(overall_row["due_this_week"]) if overall_row else 0
    }

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

# ============================================================
# 8. QISMAN TO'LOV VA MAVJUD MIJOZGA QARZ QO'SHISH
# ============================================================

async def record_customer_payment(
    customer_id: int,
    shop_id: str,
    pay_amount: float,
    admin_id: int = 0,
    note: Optional[str] = None,
    admin_name: Optional[str] = None
) -> dict:
    """Mijoz qarzidan qisman yoki to'liq to'lovni ayirib tashlash"""
    cust = await db_fetch_one("SELECT * FROM customers WHERE id = ? AND shop_id = ?", customer_id, shop_id)
    if not cust:
        raise ValueError("Mijoz topilmadi")

    total_debt = float(cust.get("total_debt") or 0.0)
    if total_debt <= 0:
        raise ValueError("Mijozda faol qarzdorlik mavjud emas")

    pay_amount = float(pay_amount)
    if pay_amount <= 0:
        raise ValueError("To'lov summasi 0 dan katta bo'lishi kerak")

    actual_pay = min(pay_amount, total_debt)
    remaining_to_deduct = actual_pay
    now_dt = datetime.now()
    default_note = note or "Qisman to'lov"
    resolved_name = resolve_admin_label(admin_id, admin_name)

    active_debts = await db_fetch_all("""
        SELECT * FROM debts 
        WHERE customer_id = ? AND shop_id = ? AND status IN ('active', 'overdue')
        ORDER BY debt_date ASC, id ASC
    """, customer_id, shop_id)

    for d in active_debts:
        if remaining_to_deduct <= 0:
            break
            
        d_id = d["id"]
        d_amount = float(d["amount"])
        
        if remaining_to_deduct >= d_amount:
            await db_execute("""
                UPDATE debts 
                SET status = 'paid', paid_date = ?, paid_amount = ?, admin_note = ?, updated_at = ?
                WHERE id = ?
            """, now_dt, d_amount, default_note, now_dt, d_id)
            
            await db_execute_insert("""
                INSERT INTO payment_history (debt_id, amount, paid_at, note, admin_id, admin_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, d_id, d_amount, now_dt, default_note, admin_id, resolved_name)
            
            remaining_to_deduct -= d_amount
        else:
            new_amount = round(d_amount - remaining_to_deduct, 2)
            await db_execute("""
                UPDATE debts 
                SET amount = ?, updated_at = ?
                WHERE id = ?
            """, new_amount, now_dt, d_id)
            
            await db_execute_insert("""
                INSERT INTO payment_history (debt_id, amount, paid_at, note, admin_id, admin_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, d_id, remaining_to_deduct, now_dt, default_note, admin_id, resolved_name)
            
            remaining_to_deduct = 0
            break

    total_row = await db_fetch_one(
        "SELECT COALESCE(SUM(amount), 0) as total FROM debts WHERE customer_id = ? AND status IN ('active', 'overdue')",
        customer_id
    )
    new_total = float(total_row["total"]) if total_row else 0.0
    await db_execute("UPDATE customers SET total_debt = ? WHERE id = ?", new_total, customer_id)

    admin = await get_admin_by_shop_id(shop_id)

    return {
        "customer": cust,
        "shop_name": admin["shop_name"] if admin else "Do'kon",
        "paid_amount": actual_pay,
        "remaining_debt": new_total,
        "admin_name": resolved_name
    }

async def add_debt_to_existing_customer(
    customer_id: int,
    shop_id: str,
    amount: float,
    description: str,
    due_date: str,
    notes: Optional[str] = None,
    admin_id: Optional[int] = None,
    admin_name: Optional[str] = None
) -> dict:
    """Mavjud mijozga yangi qarz qo'shish"""
    cust = await db_fetch_one("SELECT * FROM customers WHERE id = ? AND shop_id = ?", customer_id, shop_id)
    if not cust:
        raise ValueError("Mijoz topilmadi")

    d_date = date.today()
    d_due = date.fromisoformat(due_date) if isinstance(due_date, str) else due_date
    resolved_name = resolve_admin_label(admin_id, admin_name)
    desc_val = description.strip() if description and str(description).strip() else "Nasiya savdo"

    debt_id = await db_execute_insert("""
        INSERT INTO debts (customer_id, shop_id, amount, description, debt_date, due_date, status, admin_note, created_by_admin_id, created_by_admin_name)
        VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
    """, customer_id, shop_id, float(amount), desc_val, d_date, d_due, notes, admin_id, resolved_name)

    total_row = await db_fetch_one(
        "SELECT COALESCE(SUM(amount), 0) as total FROM debts WHERE customer_id = ? AND status IN ('active', 'overdue')",
        customer_id
    )
    new_total = float(total_row["total"]) if total_row else float(amount)
    await db_execute("UPDATE customers SET total_debt = ? WHERE id = ?", new_total, customer_id)

    admin = await get_admin_by_shop_id(shop_id)

    return {
        "customer": cust,
        "shop_name": admin["shop_name"] if admin else "Do'kon",
        "debt_id": debt_id,
        "amount": float(amount),
        "description": description.strip(),
        "due_date": str(d_due),
        "total_debt": new_total,
        "created_by_admin_name": resolved_name
    }
