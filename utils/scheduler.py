import os
import logging
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import settings
from database.queries import (
    get_debts_for_notification,
    update_overdue_statuses,
    mark_reminder_sent,
    log_notification
)
from utils.validators import format_amount, format_date_uz
from utils.formatters import esc

logger = logging.getLogger(__name__)

async def send_reminders(bot):
    """Kunlik eslatmalar — har kuni soat 09:00 da Toshkent vaqtida"""
    logger.info("⏰ Kunlik eslatmalar tekshirilmoqda...")
    
    # 1. Muddati o'tgan qarzlarni yangilash
    try:
        overdue_count = await update_overdue_statuses()
        if overdue_count > 0:
            logger.info(f"🔴 {overdue_count} ta qarz muddati o'tgan (overdue) holatiga o'tkazildi.")
    except Exception as e:
        logger.error(f"❌ Qarz holatlarini yangilashda xatolik: {e}")

    # 2. Ertaga to'lashi kerak bo'lganlar (1 kun oldin eslatma)
    try:
        tomorrow_debts = await get_debts_for_notification(days_ahead=1)
        for debt in tomorrow_debts:
            tg_id = debt.get("telegram_id")
            if not tg_id:
                continue
                
            text = (
                f"⏰ <b>Qarz to'lash eslatmasi!</b>\n\n"
                f"Assalomu alaykum, <b>{esc(debt['full_name'])}</b>! 👋\n\n"
                f"Ertaga — <b>{format_date_uz(debt['due_date'])}</b> kuni "
                f"<b>{esc(debt['shop_name'])}</b> do'koniga quyidagi qarzni to'lash muddatingiz:\n\n"
                f"💰 Summa: <b>{format_amount(debt['amount'])}</b>\n"
                f"📦 Olgan narsa: {esc(debt['description'])}\n\n"
                f"📞 Do'kon telefoni: <code>{esc(debt.get('admin_phone') or 'Bog\'lanish')}</code>\n\n"
                f"Iltimos, to'lovni o'z vaqtida amalga oshiring. Rahmat!"
            )
            try:
                await bot.send_message(chat_id=tg_id, text=text, parse_mode="HTML")
                await mark_reminder_sent(debt["id"])
                await log_notification(debt["id"], debt["customer_id"], "reminder_1day", True)
                logger.info(f"✅ 1-kunlik eslatma yuborildi: {debt['full_name']} (ID: {debt['id']})")
            except Exception as ex:
                logger.warning(f"❌ 1-kunlik eslatma yuborilmadi ({debt['full_name']}): {ex}")
                await log_notification(debt["id"], debt["customer_id"], "reminder_1day", False, str(ex))
    except Exception as e:
        logger.error(f"❌ 1-kunlik eslatmalar siklida xato: {e}")

    # 3. 3 kun oldin xabardor qilish
    try:
        three_day_debts = await get_debts_for_notification(days_ahead=3)
        for debt in three_day_debts:
            tg_id = debt.get("telegram_id")
            if not tg_id:
                continue
                
            text = (
                f"💡 <b>Oldindan eslatma</b>\n\n"
                f"Assalomu alaykum, <b>{esc(debt['full_name'])}</b>! 👋\n\n"
                f"<b>{format_date_uz(debt['due_date'])}</b> kuni (3 kundan so'ng) "
                f"<b>{esc(debt['shop_name'])}</b> do'koniga to'lov muddati:\n\n"
                f"💰 Summa: <b>{format_amount(debt['amount'])}</b>\n"
                f"📦 Olgan narsa: {esc(debt['description'])}\n\n"
                f"Eslatib o'tamiz."
            )
            try:
                await bot.send_message(chat_id=tg_id, text=text, parse_mode="HTML")
                await log_notification(debt["id"], debt["customer_id"], "reminder_3day", True)
                logger.info(f"✅ 3-kunlik eslatma yuborildi: {debt['full_name']}")
            except Exception as ex:
                logger.warning(f"❌ 3-kunlik eslatma yuborilmadi ({debt['full_name']}): {ex}")
                await log_notification(debt["id"], debt["customer_id"], "reminder_3day", False, str(ex))
    except Exception as e:
        logger.error(f"❌ 3-kunlik eslatmalar siklida xato: {e}")

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
    
    # Har kuni soat 09:00 da eslatmalar
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(hour=9, minute=0),
        args=[bot],
        id="daily_reminders",
        name="Kunlik qarz eslatmalari",
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
