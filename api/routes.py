import json
import logging
import time
from typing import Optional, Any, Dict, List
from pathlib import Path
from aiohttp import web
from config import settings
from database.queries import (
    get_admin_by_shop_id,
    get_admin_by_telegram_id,
    get_first_active_admin,
    get_admin_stats,
    get_customers_list,
    get_customer_detail,
    get_customer_by_id,
    get_customer_by_telegram_id,
    get_customer_all_debts,
    add_customer,
    mark_debt_paid,
    record_customer_payment,
    add_debt_to_existing_customer
)
from utils.validators import validate_phone, validate_amount, validate_date, validate_full_name
from utils.notifications import (
    notify_customer_partial_payment,
    notify_customer_debt_added,
    notify_customer_debt_paid
)

logger = logging.getLogger(__name__)

# CORS middleware
@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Shop-Id, X-Telegram-User-Id, X-Telegram-Init-Data"
    return response

# ============================================================
# SHOP RESOLVER HELPER
# ============================================================
_cached_default_shop_id: Optional[str] = "5832B1F2"

async def resolve_shop_id(request: web.Request) -> str:
    """Har qanday manbadan do'kon kodini tezkor aniqlash (keshlangan)"""
    global _cached_default_shop_id
    # 1. URL yo'li ({shop_id})
    shop_id = request.match_info.get("shop_id", "").strip().upper()
    if shop_id:
        return shop_id
    # 2. Query parametr (?shop_id=...)
    shop_id = request.query.get("shop_id", "").strip().upper()
    if shop_id:
        return shop_id
    # 3. Header (X-Shop-Id)
    shop_id = request.headers.get("X-Shop-Id", "").strip().upper()
    if shop_id:
        return shop_id
    # 4. Keshdagi default do'kon kodi (0ms)
    if _cached_default_shop_id:
        return _cached_default_shop_id
    # 5. Tizimdagi birinchi faol admin do'koni (fallback)
    first_admin = await get_first_active_admin()
    if first_admin:
        _cached_default_shop_id = first_admin["shop_id"]
        return _cached_default_shop_id
    return ""

# ============================================================
# API IN-MEMORY TEZKOR KESH (0ms javob berish uchun)
# ============================================================
_stats_memory_cache: Dict[str, Any] = {}
_customers_memory_cache: Dict[str, Any] = {}
CACHE_TTL = 30 # soniya (har qanday o'zgarishda darhol tozalanadi)

def invalidate_api_cache():
    """Qarz yoki to'lov o'zgarganda keshni bir zumda tozalash"""
    _stats_memory_cache.clear()
    _customers_memory_cache.clear()

# ============================================================
# API HANDLERS
# ============================================================

async def handle_get_stats(request: web.Request):
    """GET /api/stats yoki /api/stats/{shop_id}?date=YYYY-MM-DD"""
    shop_id = await resolve_shop_id(request)
    if not shop_id:
        return web.json_response({"detail": "Do'kon topilmadi"}, status=404)
        
    target_date = request.query.get("date") or "today"
    cache_key = f"{shop_id}:{target_date}"
    now = time.time()
    if cache_key in _stats_memory_cache:
        ts, cached_stats = _stats_memory_cache[cache_key]
        if now - ts < CACHE_TTL:
            return web.json_response(cached_stats)

    admin = await get_admin_by_shop_id(shop_id)
    if not admin:
        return web.json_response({"detail": "Do'kon topilmadi"}, status=404)
        
    stats = await get_admin_stats(shop_id, target_date=target_date if target_date != "today" else None)
    stats["shop_name"] = admin["shop_name"]
    stats["shop_id"] = admin["shop_id"]
    _stats_memory_cache[cache_key] = (now, stats)
    return web.json_response(stats)

async def handle_get_customers(request: web.Request):
    """GET /api/customers yoki /api/customers/{shop_id}"""
    shop_id = await resolve_shop_id(request)
    if not shop_id:
        return web.json_response([], status=200)

    search = request.query.get("search") or ""
    status_filter = request.query.get("status") or "all"
    cache_key = f"{shop_id}:{search}:{status_filter}"
    now = time.time()
    if cache_key in _customers_memory_cache:
        ts, cached_custs = _customers_memory_cache[cache_key]
        if now - ts < CACHE_TTL:
            return web.json_response(cached_custs)

    customers = await get_customers_list(shop_id, search=search if search else None, status_filter=status_filter)
    _customers_memory_cache[cache_key] = (now, customers)
    return web.json_response(customers)

async def handle_get_customer_detail(request: web.Request):
    """GET /api/customer/{customer_id}?shop_id=..."""
    try:
        customer_id = int(request.match_info.get("customer_id"))
    except (ValueError, TypeError):
        return web.json_response({"detail": "Noto'g'ri customer_id"}, status=400)
        
    shop_id = await resolve_shop_id(request)
    if not shop_id:
        return web.json_response({"detail": "shop_id ko'rsatilmadi"}, status=400)
        
    customer = await get_customer_detail(customer_id, shop_id)
    if not customer:
        return web.json_response({"detail": "Mijoz topilmadi"}, status=404)
        
    return web.json_response(customer)

async def handle_add_customer(request: web.Request):
    """POST /api/customers/add"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"detail": "Noto'g'ri JSON formati"}, status=400)
        
    shop_id = data.get("shop_id", "").strip().upper()
    if not shop_id:
        shop_id = await resolve_shop_id(request)
    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    amount = data.get("amount")
    description = data.get("description", "").strip()
    due_date = data.get("due_date", "").strip()
    notes = data.get("notes")

    # Validatsiyalar
    admin = await get_admin_by_shop_id(shop_id)
    if not admin:
        return web.json_response({"detail": "Do'kon topilmadi"}, status=404)

    is_name_ok, name_val = validate_full_name(full_name)
    if not is_name_ok:
        return web.json_response({"detail": name_val}, status=400)

    # Telefon raqam ixtiyoriy
    phone_val = None
    if phone and phone.strip():
        is_phone_ok, valid_phone = validate_phone(phone.strip())
        if not is_phone_ok:
            return web.json_response({"detail": valid_phone}, status=400)
        phone_val = valid_phone

    is_amt_ok, amt_val = validate_amount(amount)
    if not is_amt_ok:
        return web.json_response({"detail": amt_val}, status=400)

    is_date_ok, date_val = validate_date(due_date)
    if not is_date_ok:
        return web.json_response({"detail": date_val}, status=400)

    # Nima olingani (Mahsulot) ixtiyoriy
    if not description or len(description.strip()) == 0:
        description = "Nasiya savdo"

    admin_id_val = request.headers.get("X-Telegram-User-Id") or data.get("admin_id")
    admin_name_val = request.headers.get("X-Admin-Name") or data.get("admin_name")
    admin_id = int(admin_id_val) if admin_id_val and str(admin_id_val).isdigit() else 0

    result = await add_customer(
        shop_id=shop_id,
        full_name=name_val,
        phone=phone_val,
        amount=amt_val,
        description=description,
        due_date=date_val,
        notes=notes,
        admin_id=admin_id,
        admin_name=admin_name_val
    )
    invalidate_api_cache()
    return web.json_response(result)

async def handle_mark_paid(request: web.Request):
    """POST /api/debt/{debt_id}/pay"""
    try:
        debt_id = int(request.match_info.get("debt_id"))
    except (ValueError, TypeError):
        return web.json_response({"detail": "Noto'g'ri debt_id"}, status=400)
        
    try:
        data = await request.json()
    except Exception:
        data = {}
        
    shop_id = data.get("shop_id") or request.headers.get("X-Shop-Id", "").strip().upper()
    admin_id_val = request.headers.get("X-Telegram-User-Id") or data.get("admin_id")
    admin_name_val = request.headers.get("X-Admin-Name") or data.get("admin_name")
    admin_id = int(admin_id_val) if admin_id_val and str(admin_id_val).isdigit() else 0
    note = data.get("note", "Mini App orqali to'landi")
    
    if not shop_id:
        return web.json_response({"detail": "shop_id ko'rsatilmadi"}, status=400)
        
    res = await mark_debt_paid(debt_id, shop_id, admin_id, note, admin_name=admin_name_val)
    if not res:
        return web.json_response({"detail": "Qarz topilmadi yoki do'kon mos kelmadi"}, status=400)

    # Bildirishnomani fonda yuboramiz (foydalanuvchi kutib turmaydi, tez ishlaydi)
    import asyncio
    asyncio.create_task(notify_customer_debt_paid(
        customer=res["customer"],
        shop_name=res["shop_name"],
        debt_amount=res["paid_amount"],
        description=res["debt"]["description"],
        remaining_debt=res["remaining_debt"]
    ))
        
    invalidate_api_cache()
    return web.json_response({
        "success": True,
        "paid_amount": res["paid_amount"],
        "remaining_debt": res["remaining_debt"],
        "admin_name": res.get("admin_name")
    })

async def handle_customer_pay(request: web.Request):
    """POST /api/customer/{customer_id}/pay — Qarzdan ma'lum summani ayirish"""
    try:
        customer_id = int(request.match_info.get("customer_id"))
    except (ValueError, TypeError):
        return web.json_response({"detail": "Noto'g'ri customer_id"}, status=400)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"detail": "Noto'g'ri JSON format"}, status=400)

    shop_id = data.get("shop_id") or request.headers.get("X-Shop-Id", "").strip().upper()
    if not shop_id:
        shop_id = await resolve_shop_id(request)

    amount = data.get("amount")
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError()
    except Exception:
        return web.json_response({"detail": "To'lov summasi noto'g'ri"}, status=400)

    note = data.get("note", "Mini App orqali to'landi")
    admin_id_val = request.headers.get("X-Telegram-User-Id") or data.get("admin_id")
    admin_name_val = request.headers.get("X-Admin-Name") or data.get("admin_name")
    admin_id = int(admin_id_val) if admin_id_val and str(admin_id_val).isdigit() else 0

    try:
        result = await record_customer_payment(customer_id, shop_id, amount, admin_id, note, admin_name=admin_name_val)
    except ValueError as e:
        return web.json_response({"detail": str(e)}, status=400)

    # Bildirishnomani fonda yuborish
    import asyncio
    asyncio.create_task(notify_customer_partial_payment(
        customer=result["customer"],
        shop_name=result["shop_name"],
        paid_amount=result["paid_amount"],
        remaining_debt=result["remaining_debt"]
    ))

    invalidate_api_cache()
    return web.json_response({
        "success": True,
        "paid_amount": result["paid_amount"],
        "remaining_debt": result["remaining_debt"],
        "admin_name": result.get("admin_name")
    })

async def handle_customer_add_debt(request: web.Request):
    """POST /api/customer/{customer_id}/add-debt — Mijozga yangi qarz qo'shish"""
    try:
        customer_id = int(request.match_info.get("customer_id"))
    except (ValueError, TypeError):
        return web.json_response({"detail": "Noto'g'ri customer_id"}, status=400)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"detail": "Noto'g'ri JSON format"}, status=400)

    shop_id = data.get("shop_id") or request.headers.get("X-Shop-Id", "").strip().upper()
    if not shop_id:
        shop_id = await resolve_shop_id(request)

    amount = data.get("amount")
    description = (data.get("description") or "").strip()
    due_date = (data.get("due_date") or "").strip()
    notes = data.get("notes")

    is_amt_ok, amt_val = validate_amount(amount)
    if not is_amt_ok:
        return web.json_response({"detail": amt_val}, status=400)

    if not description or len(description.strip()) == 0:
        description = "Nasiya savdo"

    is_date_ok, date_val = validate_date(due_date)
    if not is_date_ok:
        return web.json_response({"detail": date_val}, status=400)

    admin_id_val = request.headers.get("X-Telegram-User-Id") or data.get("admin_id")
    admin_name_val = request.headers.get("X-Admin-Name") or data.get("admin_name")
    admin_id = int(admin_id_val) if admin_id_val and str(admin_id_val).isdigit() else 0

    try:
        result = await add_debt_to_existing_customer(customer_id, shop_id, amt_val, description, date_val, notes, admin_id=admin_id, admin_name=admin_name_val)
    except ValueError as e:
        return web.json_response({"detail": str(e)}, status=400)

    # Bildirishnomani fonda yuborish
    import asyncio
    asyncio.create_task(notify_customer_debt_added(
        customer=result["customer"],
        shop_name=result["shop_name"],
        amount=result["amount"],
        description=result["description"],
        due_date=result["due_date"],
        total_debt=result["total_debt"]
    ))

    invalidate_api_cache()
    return web.json_response({
        "success": True,
        "debt_id": result["debt_id"],
        "total_debt": result["total_debt"],
        "admin_name": result.get("created_by_admin_name")
    })

async def handle_get_me(request: web.Request):
    """Foydalanuvchi roli va ma'lumotlarini aniqlash (Admin yoki Mijoz)"""
    role_param = request.query.get("role", "").strip().lower()
    cust_id_param = request.query.get("customer_id")
    user_id_str = request.headers.get("X-Telegram-User-Id") or request.query.get("user_id")
    
    # 1. To'g'ridan-to'g'ri customer_id berilgan bo'lsa
    if cust_id_param and cust_id_param.isdigit():
        cust = await get_customer_by_id(int(cust_id_param))
        if cust:
            debts = await get_customer_all_debts(int(cust_id_param))
            return web.json_response({
                "role": "customer",
                "customer": cust,
                "debts": debts
            })

    # 2. Telegram user ID orqali aniqlash
    if user_id_str and user_id_str.isdigit():
        uid = int(user_id_str)
        admin = await get_admin_by_telegram_id(uid)
        if not admin and settings.is_admin_id(uid):
            try:
                admin = await get_first_active_admin()
            except Exception:
                pass
                
        if admin:
            return web.json_response({
                "role": "admin",
                "admin": admin,
                "shop_id": admin["shop_id"]
            })
            
        custs = await get_customer_by_telegram_id(uid)
        if custs:
            cust = custs[0]
            debts = await get_customer_all_debts(cust["id"])
            return web.json_response({
                "role": "customer",
                "customer": cust,
                "debts": debts
            })

    # 3. Fallback: agar role=customer bo'lsa
    if role_param == "customer":
        return web.json_response({
            "role": "customer",
            "customer": None,
            "debts": []
        })

    # 4. Standart holatda Admin do'koni
    shop_id = await resolve_shop_id(request)
    admin = await get_admin_by_shop_id(shop_id)
    return web.json_response({
        "role": "admin",
        "admin": admin,
        "shop_id": shop_id
    })

async def handle_index(request: web.Request):
    """Mini App index.html faylini ko'rsatish (keshlanmaslik kafolati bilan)"""
    index_file = Path("mini_app/index.html").absolute()
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        return web.Response(
            text=content,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return web.Response(text="Mini App topilmadi", status=404)

async def handle_favicon(request: web.Request):
    """Favicon so'rovini qondirish"""
    return web.Response(text="", content_type="image/x-icon")

def create_web_app() -> web.Application:
    """Aiohttp veb ilovasini yaratish"""
    app = web.Application(middlewares=[cors_middleware])
    
    # API endpoints
    app.router.add_get("/favicon.ico", handle_favicon)
    app.router.add_get("/api/me", handle_get_me)
    app.router.add_get("/api/auth/me", handle_get_me)
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_get("/api/stats/", handle_get_stats)
    app.router.add_get("/api/stats/{shop_id}", handle_get_stats)
    app.router.add_get("/api/customers", handle_get_customers)
    app.router.add_get("/api/customers/", handle_get_customers)
    app.router.add_get("/api/customers/{shop_id}", handle_get_customers)
    app.router.add_get("/api/customer/{customer_id}", handle_get_customer_detail)
    app.router.add_post("/api/customer/{customer_id}/pay", handle_customer_pay)
    app.router.add_post("/api/customer/{customer_id}/add-debt", handle_customer_add_debt)
    app.router.add_post("/api/customers/add", handle_add_customer)
    app.router.add_post("/api/debt/{debt_id}/pay", handle_mark_paid)
    
    # Static files & Mini App
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    
    mini_app_dir = Path("mini_app").absolute()
    if mini_app_dir.exists():
        css_dir = mini_app_dir / "css"
        js_dir = mini_app_dir / "js"
        if css_dir.exists():
            app.router.add_static("/css/", path=css_dir)
        if js_dir.exists():
            app.router.add_static("/js/", path=js_dir)
        app.router.add_static("/static/", path=mini_app_dir)
        
    return app

