import os
import logging
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import settings
from database.queries import (
    get_all_customers_with_active_debts,
    update_overdue_statuses,
    mark_reminder_sent,
    log_notification
)
from utils.validators import format_amount, format_date_uz
from utils.formatters import esc

logger = logging.getLogger(__name__)

def build_daily_reminder_text(cust: dict) -> str:
    """Qarzdor mijoz uchun 19:00 eslatma matni"""
    total_str = format_amount(cust["total_debt"])
    shop_name = esc(cust["shop_name"])
    name = esc(cust["full_name"])
    
    debts = cust.get("debts", [])
    debts_lines = []
    has_overdue = False
    
    for d in debts[:5]:
        due = format_date_uz(d["due_date"])
        amt = format_amount(d["amount"])
        desc = esc(d.get("description") or "Nasiya savdo")
        if d.get("status") == "overdue":
            has_overdue = True
            badge = "⚠️ (Muddati o'tgan)"
        else:
            badge = f"(Muddat: {due})"
        debts_lines.append(f"  • <b>{desc}</b>: {amt} {badge}")
        
    if len(debts) > 5:
        debts_lines.append(f"  <i>...va yana {len(debts) - 5} ta qarz</i>")
        
    debts_block = "\n".join(debts_lines) if debts_lines else "  • Faol qarzdorlik"
    admin_phone = cust.get("admin_phone")
    phone_line = f"\n📞 <b>Do'kon telefoni:</b> <code>{esc(admin_phone)}</code>" if admin_phone else ""
    overdue_warning = "\n⚠️ <i>Diqqat: Ba'zi to'lovlaringiz muddati o'tib ketgan!</i>" if has_overdue else ""

    text = (
        f"⏰ <b>Qarzdorlik eslatmasi!</b>\n\n"
        f"Assalomu alaykum, <b>{name}</b>! 👋\n\n"
        f"Sizning <b>{shop_name}</b> do'konidan qarzdorligingiz mavjud.\n"
        f"Iltimos, qarzingizni to'lashingizni so'raymiz:\n\n"
        f"💰 <b>Jami qarzingiz:</b> <b>{total_str}</b>\n\n"
        f"📦 <b>Qarzlar ro'yxati:</b>\n"
        f"{debts_block}"
        f"{overdue_warning}\n"
        f"{phone_line}\n\n"
        f"Barcha hisob-kitoblarni ko'rish uchun quyidagi tugmani bosing:"
    )
    return text

async def send_reminders(bot) -> dict:
    """Kunlik eslatmalar — har kuni kechqurun soat 19:00 da Toshkent vaqtida barcha qarzdorlarga"""
    logger.info("⏰ Kunlik eslatmalar (19:00) yuborilishi boshlandi...")
    
    # 1. Muddati o'tgan qarzlarni yangilash
    try:
        overdue_count = await update_overdue_statuses()
        if overdue_count > 0:
            logger.info(f"🔴 {overdue_count} ta qarz muddati o'tgan (overdue) holatiga o'tkazildi.")
    except Exception as e:
        logger.error(f"❌ Qarz holatlarini yangilashda xatolik: {e}")

    # 2. Qarzi bor barcha mijozlarni olish
    try:
        customers = await get_all_customers_with_active_debts()
    except Exception as e:
        logger.error(f"❌ Qarzdor mijozlarni olishda xatolik: {e}")
        return {"total": 0, "sent": 0, "failed": 0, "error": str(e)}

    sent_count = 0
    fail_count = 0
    
    for cust in customers:
        tg_id = cust.get("telegram_id")
        if not tg_id:
            continue
            
        text = build_daily_reminder_text(cust)
        web_app_url = f"{settings.MINI_APP_URL}/?role=customer&tg_id={tg_id}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Mening qarzlarim (Mini App)", web_app=WebAppInfo(url=web_app_url))]
        ])
        
        try:
            await bot.send_message(
                chat_id=tg_id, 
                text=text, 
                parse_mode="HTML", 
                reply_markup=keyboard
            )
            sent_count += 1
            for d in cust.get("debts", []):
                await mark_reminder_sent(d["debt_id"])
                await log_notification(d["debt_id"], cust["customer_id"], "daily_19pm", True)
            logger.info(f"✅ 19:00 eslatma yuborildi: {cust['full_name']} (TG: {tg_id})")
        except Exception as ex:
            fail_count += 1
            logger.warning(f"❌ 19:00 eslatma yuborilmadi ({cust['full_name']}): {ex}")
            for d in cust.get("debts", []):
                await log_notification(d["debt_id"], cust["customer_id"], "daily_19pm", False, str(ex))

    logger.info(f"⏰ 19:00 eslatmalar yakunlandi: Jami: {len(customers)}, Yuborildi: {sent_count}, Xato: {fail_count}")
    return {"total": len(customers), "sent": sent_count, "failed": fail_count}

async def keep_alive_ping():
    """Render Free tier'da server 15 daqiqada uxlab qolmasligi uchun doimiy ping"""
    url = os.getenv("RENDER_EXTERNAL_URL") or settings.MINI_APP_URL
    if url and url.startswith("https://"):
        try:
            target = f"{url.rstrip('/')}/favicon.ico"
            async with aiohttp.ClientSession() as session:
                async with session.get(target, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    logger.debug(f"Keep-alive ping muvaffaqiyatli: {resp.status}")
        except Exception:
            pass

def setup_scheduler(bot) -> AsyncIOScheduler:
    """Scheduler yaratish va ishga sozlash"""
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    
    # Har kuni kechqurun soat 19:00 da barcha qarzdor mijozlarga eslatma
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(hour=19, minute=0, timezone="Asia/Tashkent"),
        args=[bot],
        id="daily_reminders_19pm",
        name="Har kuni 19:00 qarz eslatmalari",
        replace_existing=True,
        misfire_grace_time=3600
    )
    
    # Har 10 daqiqada Render Free uxlab qolmasligi uchun keep-alive
    scheduler.add_job(
        keep_alive_ping,
        trigger="interval",
        minutes=10,
        id="render_keep_alive",
        name="Render Keep Alive Ping",
        replace_existing=True
    )
    
    return scheduler
