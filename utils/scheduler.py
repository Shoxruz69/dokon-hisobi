import os
import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import settings
from database.db import db_fetch_all
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
    shop_name = esc(cust.get("shop_name") or "Do'kon")
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

def build_admin_summary_messages(shop_name: str, total_count: int, total_amount: float,
                                 sent_list: list, unlinked_list: list, failed_list: list) -> List[str]:
    """Admin uchun 19:00 xabarnomasi — kimlarga bordi, kimlarga bormadi"""
    now_dt = datetime.now(ZoneInfo("Asia/Tashkent"))
    date_str = now_dt.strftime("%d.%m.%Y")
    
    total_not_sent = len(unlinked_list) + len(failed_list)
    
    summary_header = (
        f"⏰ <b>19:00 KUNLIK QARZDORLIK ESLATMALARI HISOBOTI</b>\n"
        f"🏪 Do'kon: <b>{esc(shop_name)}</b>\n"
        f"📅 Sana: <b>{date_str} | 19:00</b>\n\n"
        f"📊 <b>Umumiy natijalar:</b>\n"
        f"• Qarzdorlar soni: <b>{total_count} ta</b>\n"
        f"• 💰 Jami qarzdorlik: <b>{format_amount(total_amount)}</b>\n"
        f"• 🟢 <b>SMS borganlar:</b> <b>{len(sent_list)} ta</b>\n"
        f"• ⚠️ <b>SMS bormaganlar:</b> <b>{total_not_sent} ta</b>\n"
    )
    
    if total_count == 0:
        return [summary_header + "\n✅ <i>Bugun do'konda faol qarzdorliklar mavjud emas. Barcha hisob-kitoblar joyida!</i>"]
        
    lines = []
    
    # 1. SMS BORGANLAR
    if sent_list:
        lines.append(f"\n🟢 <b>SMS (eslatma) borgan mijozlar ({len(sent_list)} ta):</b>")
        for i, c in enumerate(sent_list, 1):
            phone_str = f" ({c['phone']})" if c.get("phone") else ""
            lines.append(f"{i}. <b>{esc(c['name'])}</b>{esc(phone_str)} — <b>{format_amount(c['debt'])}</b>")
            
    # 2. BOTGA ULANMAGANLAR (TELEGRAM ID YO'Q)
    if unlinked_list:
        lines.append(f"\n🟡 <b>SMS bormagan — Botga ulanmaganlar ({len(unlinked_list)} ta):</b>")
        for i, c in enumerate(unlinked_list, 1):
            phone_str = f" ({c['phone']})" if c.get("phone") else ""
            lines.append(f"{i}. <b>{esc(c['name'])}</b>{esc(phone_str)} — <b>{format_amount(c['debt'])}</b> <i>(Botni ochmagan)</i>")
            
    # 3. YUBORISHDA XATOLIK BO'LGANLAR (MASALAN BOT BLOKLANGAN)
    if failed_list:
        lines.append(f"\n🔴 <b>SMS bormagan — Xatolik bo'lganlar ({len(failed_list)} ta):</b>")
        for i, c in enumerate(failed_list, 1):
            phone_str = f" ({c['phone']})" if c.get("phone") else ""
            reason_str = f" — <i>{esc(c.get('reason', 'Xato'))}</i>"
            lines.append(f"{i}. <b>{esc(c['name'])}</b>{esc(phone_str)} — <b>{format_amount(c['debt'])}</b>{reason_str}")

    footer = "\n💡 <i>Mijozlarga botingiz orqali telefon raqamlarini tasdiqlashlarini aytsangiz, ularga ham har kuni 19:00 da avtomatik eslatma boradi.</i>"
    
    # Bo'laklarga ajratish (har bir xabar < 3800 belgi)
    messages = []
    current_msg = summary_header
    for line in lines:
        if len(current_msg) + len(line) + 2 > 3800:
            messages.append(current_msg.strip())
            current_msg = f"⏰ <b>19:00 HISOBOT (davomi):</b>\n" + line + "\n"
        else:
            current_msg += line + "\n"
            
    if len(current_msg) + len(footer) > 4000:
        messages.append(current_msg.strip())
        messages.append(footer.strip())
    else:
        current_msg += footer
        messages.append(current_msg.strip())
        
    return messages

async def get_shop_admin_ids(shop_id: str, manual_admin_id: Optional[int] = None) -> List[int]:
    """Do'kon adminlari va tizim adminlari ro'yxati"""
    admin_ids = set()
    if manual_admin_id:
        admin_ids.add(int(manual_admin_id))
    for aid in settings.get_admin_ids():
        admin_ids.add(aid)
    try:
        db_admins = await db_fetch_all(
            "SELECT telegram_id FROM admins WHERE is_active = TRUE AND (shop_id = ? OR shop_id IS NULL)", 
            shop_id
        )
        for a in db_admins:
            tid = a.get("telegram_id")
            if tid:
                try:
                    admin_ids.add(int(tid))
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Admin ID larni olishda xatolik: {e}")
    return list(admin_ids)

async def send_reminders(bot, manual_admin_id: Optional[int] = None) -> dict:
    """Kunlik eslatmalar — har kuni kechqurun soat 19:00 da Toshkent vaqtida barcha qarzdorlarga
       va har bir adminning o'ziga kimlarga bordi / kimlarga bormadi hisoboti"""
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
        return {"total": 0, "sent": 0, "failed": 0, "unlinked": 0, "error": str(e)}

    # Do'konlar bo'yicha guruhlash
    shops_data: Dict[str, dict] = {}
    
    for cust in customers:
        shop_id = cust.get("shop_id") or "5832B1F2"
        if shop_id not in shops_data:
            shops_data[shop_id] = {
                "shop_name": cust.get("shop_name") or "Do'kon",
                "total_debt": 0.0,
                "sent": [],
                "unlinked": [],
                "failed": []
            }
            
        c_name = cust.get("full_name") or "Mijoz"
        c_phone = cust.get("phone") or ""
        c_debt = float(cust.get("total_debt") or 0)
        tg_id = cust.get("telegram_id")
        
        shops_data[shop_id]["total_debt"] += c_debt
        
        # Telegram ID yo'q bo'lsa -> SMS bormadi (botga ulanmagan)
        if not tg_id:
            shops_data[shop_id]["unlinked"].append({
                "name": c_name,
                "phone": c_phone,
                "debt": c_debt,
                "reason": "Botga kirmagan / ulanmagan"
            })
            continue
            
        # Telegram ID bor bo'lsa -> xabar yuborish
        text = build_daily_reminder_text(cust)
        web_app_url = f"{settings.MINI_APP_URL}?role=customer&customer_id={cust['customer_id']}&v=2.3"
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
            shops_data[shop_id]["sent"].append({
                "name": c_name,
                "phone": c_phone,
                "debt": c_debt,
                "tg_id": tg_id
            })
            for d in cust.get("debts", []):
                await mark_reminder_sent(d["debt_id"])
                await log_notification(d["debt_id"], cust["customer_id"], "daily_19pm", True)
            logger.info(f"✅ 19:00 eslatma yuborildi: {c_name} (TG: {tg_id})")
        except Exception as ex:
            err_str = str(ex)
            if "blocked" in err_str.lower():
                reason = "Botni bloklagan"
            elif "deactivated" in err_str.lower() or "not found" in err_str.lower():
                reason = "Akkaunt o'chirilgan"
            else:
                reason = "Telegram xatosi"
                
            shops_data[shop_id]["failed"].append({
                "name": c_name,
                "phone": c_phone,
                "debt": c_debt,
                "tg_id": tg_id,
                "reason": reason
            })
            for d in cust.get("debts", []):
                await log_notification(d["debt_id"], cust["customer_id"], "daily_19pm", False, err_str)
            logger.warning(f"❌ 19:00 eslatma yuborilmadi ({c_name}): {ex}")

    # Agar umuman qarzdor bo'lmasa, default shop uchun hisobot tayyorlash
    if not shops_data:
        shops_data["5832B1F2"] = {
            "shop_name": "Do'kon",
            "total_debt": 0.0,
            "sent": [],
            "unlinked": [],
            "failed": []
        }

    # 3. Har bir do'kon adminlariga to'liq hisobotni yuborish
    total_sent = 0
    total_unlinked = 0
    total_failed = 0
    
    for shop_id, sdata in shops_data.items():
        sent_list = sdata["sent"]
        unlinked_list = sdata["unlinked"]
        failed_list = sdata["failed"]
        total_shop_debtors = len(sent_list) + len(unlinked_list) + len(failed_list)
        
        total_sent += len(sent_list)
        total_unlinked += len(unlinked_list)
        total_failed += len(failed_list)
        
        admin_ids = await get_shop_admin_ids(shop_id, manual_admin_id)
        report_messages = build_admin_summary_messages(
            shop_name=sdata["shop_name"],
            total_count=total_shop_debtors,
            total_amount=sdata["total_debt"],
            sent_list=sent_list,
            unlinked_list=unlinked_list,
            failed_list=failed_list
        )
        
        for aid in admin_ids:
            for r_msg in report_messages:
                try:
                    await bot.send_message(chat_id=aid, text=r_msg, parse_mode="HTML")
                except Exception as aex:
                    logger.warning(f"⚠️ Admin ({aid}) ga hisobot yuborilmadi: {aex}")
                    
    logger.info(
        f"⏰ 19:00 eslatmalar yakunlandi: Jami: {len(customers)}, "
        f"Yuborildi: {total_sent}, Botga ulanmagan: {total_unlinked}, Xato: {total_failed}"
    )
    return {
        "total": len(customers),
        "sent": total_sent,
        "unlinked": total_unlinked,
        "failed": total_failed
    }

async def keep_alive_ping():
    """Render Free tier'da server 15 daqiqada uxlab qolmasligi uchun doimiy ping"""
    url = os.getenv("RENDER_EXTERNAL_URL") or settings.MINI_APP_URL
    if url and url.startswith("https://"):
        targets = [
            f"{url.rstrip('/')}/favicon.ico",
            f"{url.rstrip('/')}/"
        ]
        async with aiohttp.ClientSession() as session:
            for target in targets:
                try:
                    async with session.get(target, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        logger.debug(f"Keep-alive ping ({target}): {resp.status}")
                except Exception:
                    pass

def setup_scheduler(bot) -> AsyncIOScheduler:
    """Scheduler yaratish va ishga sozlash"""
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    
    # Har kuni kechqurun soat 19:00 da barcha qarzdor mijozlarga eslatma va adminga hisobot
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(hour=19, minute=0, timezone="Asia/Tashkent"),
        args=[bot],
        id="daily_reminders_19pm",
        name="Har kuni 19:00 qarz eslatmalari va Admin hisoboti",
        replace_existing=True,
        misfire_grace_time=7200
    )
    
    # Har 5 daqiqada Render Free uxlab qolmasligi uchun keep-alive
    scheduler.add_job(
        keep_alive_ping,
        trigger="interval",
        minutes=5,
        id="render_keep_alive",
        name="Render Keep Alive Ping",
        replace_existing=True
    )
    
    return scheduler
