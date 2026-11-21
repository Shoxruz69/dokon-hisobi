import os
import logging
import asyncio
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import settings
from database.db import db_fetch_all, db_fetch_one
from database.queries import (
    get_all_customers_with_active_debts,
    update_overdue_statuses,
    mark_reminder_sent,
    log_notification
)
from utils.validators import format_amount, format_date_uz
from utils.formatters import esc

logger = logging.getLogger(__name__)

def build_daily_reminder_text(cust: dict, days_overdue: int = 0) -> str:
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
            badge = "⚠️ (3 kundan beri to'lanmagan)"
        else:
            badge = f"(Muddat: {due})"
        debts_lines.append(f"  • <b>{desc}</b>: {amt} {badge}")
        
    if len(debts) > 5:
        debts_lines.append(f"  <i>...va yana {len(debts) - 5} ta qarz</i>")
        
    debts_block = "\n".join(debts_lines) if debts_lines else "  • Faol qarzdorlik"
    admin_phone = cust.get("admin_phone")
    phone_line = f"\n📞 <b>Do'kon telefoni:</b> <code>{esc(admin_phone)}</code>" if admin_phone else ""
    
    if days_overdue >= 3:
        overdue_warning = f"\n⚠️ <b>Diqqat: Qarzingiz to'lov muddati {days_overdue} kundan beri kechikmoqda!</b> Iltimos, qarzingizni imkon qadar tezroq to'lashingizni so'raymiz."
    elif has_overdue:
        overdue_warning = "\n⚠️ <b>Diqqat: Qarzingiz 3 kundan beri to'lanmagan!</b>"
    else:
        overdue_warning = ""

    text = (
        f"⏰ <b>Qarzdorlik eslatmasi!</b>\n\n"
        f"Assalomu alaykum, <b>{name}</b>! 👋\n\n"
        f"Sizning <b>{shop_name}</b> do'konidan qarzdorligingiz mavjud.\n"
        f"Iltimos, qarzingizni to'lashingizni so'raymiz:\n\n"
        f"💰 <b>Jami qarzingiz:</b> <b>{total_str}</b>\n\n"
        f"📦 <b>Qarzlar ro'yxati:</b>\n"
        f"{debts_block}\n"
        f"{overdue_warning}\n"
        f"{phone_line}\n\n"
        f"Barcha hisob-kitoblarni ko'rish uchun quyidagi tugmani bosing:"
    )
    return text

async def should_send_sms_to_customer(customer_id: int, total_overdue_count: int, is_manual: bool = False) -> tuple[bool, str]:
    """
    3 kundan beri to'lamaganlar uchun SMS yuborish qoidasi:
    1. Agar umumiy 3 kundan beri to'lamaganlar soni >= 3 ta bo'lsa -> har kuni avto SMS yuboriladi.
    2. Agar 3 tadan kam bo'lsa (1 yoki 2 ta) -> 2 kunda bir marta SMS yuboriladi.
    """
    if is_manual:
        return True, "Admin qo'lda yubordi"
        
    if total_overdue_count >= 3:
        return True, f"Qarzdorlar soni {total_overdue_count} >= 3 ta (har kunlik avto-SMS)"
        
    # Agar 3 tadan kam bo'lsa -> oxirgi muvaffaqiyatli SMS vaqtini tekshirish
    last_log = await db_fetch_one("""
        SELECT sent_at FROM notifications_log
        WHERE customer_id = ? AND type = 'daily_19pm' AND success = TRUE
        ORDER BY id DESC LIMIT 1
    """, customer_id)
    
    if not last_log or not last_log.get("sent_at"):
        return True, "Oxirgi 2 kunda SMS yuborilmagan (birinchi yuborish)"
        
    sent_at_val = last_log["sent_at"]
    if isinstance(sent_at_val, str):
        try:
            sent_dt = datetime.fromisoformat(sent_at_val.replace("Z", "+00:00"))
        except Exception:
            sent_dt = datetime.now(ZoneInfo("Asia/Tashkent"))
    elif isinstance(sent_at_val, datetime):
        sent_dt = sent_at_val
    else:
        return True, "Yuboriladi"
        
    now_dt = datetime.now(sent_dt.tzinfo if sent_dt.tzinfo else ZoneInfo("Asia/Tashkent"))
    days_diff = (now_dt.date() - sent_dt.date()).days
    
    if days_diff >= 2:
        return True, f"Oxirgi SMS dan {days_diff} kun o'tdi (2 kunda 1 marta qoidasi)"
    else:
        return False, "Kecha SMS yuborilgan (2 kunda 1 marta qoidasi bo'yicha bugun oraliq kun)"

def build_admin_summary_messages(shop_name: str, total_count: int, total_amount: float,
                                 overdue_3days_list: list, sent_list: list, 
                                 skipped_list: list, unlinked_list: list, 
                                 failed_list: list) -> List[str]:
    """Admin uchun 19:00 xabarnomasi — 3 kundan beri to'lamaganlar ro'yxati va SMS hisoboti"""
    now_dt = datetime.now(ZoneInfo("Asia/Tashkent"))
    date_str = now_dt.strftime("%d.%m.%Y")
    
    total_overdue = len(overdue_3days_list)
    total_overdue_sum = sum(float(c.get("debt", 0)) for c in overdue_3days_list)
    total_not_sent = len(unlinked_list) + len(failed_list)
    
    if total_overdue >= 3:
        sms_rule_desc = f"Har kunlik avto-SMS (3 kundan beri to'lamaganlar: {total_overdue} ta >= 3)"
    elif total_overdue > 0:
        sms_rule_desc = f"2 kunda 1 marta avto-SMS (3 kundan beri to'lamaganlar: {total_overdue} ta < 3)"
    else:
        sms_rule_desc = "3 kundan beri to'lamaganlar yo'q"
        
    summary_header = (
        f"⏰ <b>19:00 KUNLIK QARZDORLIK VA ESLATMALAR HISOBOTI</b>\n"
        f"🏪 Do'kon: <b>{esc(shop_name)}</b>\n"
        f"📅 Sana: <b>{date_str} | 19:00</b>\n\n"
        f"📊 <b>Umumiy natijalar:</b>\n"
        f"• Jami qarzdorlar: <b>{total_count} ta</b> (💰 <b>{format_amount(total_amount)}</b>)\n"
        f"• 🚨 <b>3 kundan beri to'lamaganlar:</b> <b>{total_overdue} ta</b> (💰 <b>{format_amount(total_overdue_sum)}</b>)\n"
        f"• ⚙️ <b>SMS tartibi:</b> <i>{sms_rule_desc}</i>\n"
        f"• 🟢 <b>SMS borganlar:</b> <b>{len(sent_list)} ta</b>\n"
        f"• ⏸️ <b>2 kunda bir rejimidagilar:</b> <b>{len(skipped_list)} ta</b>\n"
        f"• ⚠️ <b>SMS bormaganlar:</b> <b>{total_not_sent} ta</b>\n"
    )
    
    if total_count == 0 and total_overdue == 0:
        return [summary_header + "\n✅ <i>Bugun do'konda faol qarzdorliklar mavjud emas. Barcha hisob-kitoblar joyida!</i>"]
        
    lines = []
    
    # 1. 3 KUNDAN BERI TO'LAMAGANLARNING TO'LIQ RO'YXATI (FOYDALANUVCHI TALABI)
    if overdue_3days_list:
        lines.append(f"\n🚨 <b>3 kundan beri qarzini to'lamagan mijozlar ro'yxati ({len(overdue_3days_list)} ta):</b>")
        for i, c in enumerate(overdue_3days_list, 1):
            phone_str = f" ({c['phone']})" if c.get("phone") else ""
            days_str = f"<b>{c.get('days_overdue', 3)} kundan beri to'lamagan</b>"
            lines.append(f"{i}. <b>{esc(c['name'])}</b>{esc(phone_str)} — <b>{format_amount(c['debt'])}</b> ({days_str})")
    else:
        lines.append("\n✅ <i>3 kundan beri to'lamagan qarzdorlar mavjud emas!</i>")
        
    # 2. SMS BORGANLAR
    if sent_list:
        lines.append(f"\n🟢 <b>SMS (eslatma) borgan mijozlar ({len(sent_list)} ta):</b>")
        for i, c in enumerate(sent_list, 1):
            phone_str = f" ({c['phone']})" if c.get("phone") else ""
            days_info = f" ({c.get('days_overdue')} kundan beri to'lamagan)" if c.get('days_overdue') else ""
            lines.append(f"{i}. <b>{esc(c['name'])}</b>{esc(phone_str)} — <b>{format_amount(c['debt'])}</b>{days_info}")
            
    # 3. 2 KUNDA BIR REJIMIDAGI ORALIQ KUN
    if skipped_list:
        lines.append(f"\n⏸️ <b>2 kunda 1 marta qoidasi bo'yicha bugun oraliq kun ({len(skipped_list)} ta):</b>")
        for i, c in enumerate(skipped_list, 1):
            phone_str = f" ({c['phone']})" if c.get("phone") else ""
            lines.append(f"{i}. <b>{esc(c['name'])}</b>{esc(phone_str)} — <b>{format_amount(c['debt'])}</b> <i>(Kecha yuborilgan, navbatdagi ertaga)</i>")
            
    # 4. BOTGA ULANMAGANLAR (TELEGRAM ID YO'Q)
    if unlinked_list:
        lines.append(f"\n🟡 <b>SMS bormagan — Botga ulanmaganlar ({len(unlinked_list)} ta):</b>")
        for i, c in enumerate(unlinked_list, 1):
            phone_str = f" ({c['phone']})" if c.get("phone") else ""
            days_info = f" ({c.get('days_overdue')} kundan beri to'lamagan)" if c.get('days_overdue') else ""
            lines.append(f"{i}. <b>{esc(c['name'])}</b>{esc(phone_str)} — <b>{format_amount(c['debt'])}</b>{days_info} <i>(Botni ochmagan)</i>")
            
    # 5. YUBORISHDA XATOLIK BO'LGANLAR (MASALAN BOT BLOKLANGAN)
    if failed_list:
        lines.append(f"\n🔴 <b>SMS bormagan — Xatolik bo'lganlar ({len(failed_list)} ta):</b>")
        for i, c in enumerate(failed_list, 1):
            phone_str = f" ({c['phone']})" if c.get("phone") else ""
            reason_str = f" — <i>{esc(c.get('reason', 'Xato'))}</i>"
            lines.append(f"{i}. <b>{esc(c['name'])}</b>{esc(phone_str)} — <b>{format_amount(c['debt'])}</b>{reason_str}")

    footer = "\n💡 <i>Mijozlarga bot orqali telefon raqamlarini tasdiqlashlarini aytsangiz, ularga ham avtomatik eslatma boradi.</i>"
    
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
    """Kunlik eslatmalar — har kuni kechqurun soat 19:00 da Toshkent vaqtida
    va har bir adminning o'ziga 3 kundan beri to'lamaganlar ro'yxati va SMS hisoboti"""
    logger.info("⏰ Kunlik eslatmalar (19:00) yuborilishi boshlandi...")
    
    # 1. 3 kundan oshgan qarzlarni yangilash
    try:
        overdue_count = await update_overdue_statuses()
        if overdue_count > 0:
            logger.info("🔴 Qarzlar muddati (3 kundan beri to'lamagan) yangilandi.")
    except Exception as e:
        logger.error(f"❌ Qarz holatlarini yangilashda xatolik: {e}")

    # 2. Qarzi bor barcha mijozlarni olish
    try:
        customers = await get_all_customers_with_active_debts()
    except Exception as e:
        logger.error(f"❌ Qarzdor mijozlarni olishda xatolik: {e}")
        return {"total": 0, "overdue_3days": 0, "sent": 0, "skipped_2day": 0, "failed": 0, "unlinked": 0, "error": str(e)}

    today_dt = datetime.now(ZoneInfo("Asia/Tashkent")).date()

    # Do'konlar bo'yicha guruhlash
    shops_data: Dict[str, dict] = {}
    
    for cust in customers:
        shop_id = cust.get("shop_id") or "5832B1F2"
        if shop_id not in shops_data:
            shops_data[shop_id] = {
                "shop_name": cust.get("shop_name") or "Do'kon",
                "total_debt": 0.0,
                "customers": [],
                "overdue_3days": [],
                "sent": [],
                "skipped_2day": [],
                "unlinked": [],
                "failed": []
            }
            
        c_name = cust.get("full_name") or "Mijoz"
        c_phone = cust.get("phone") or ""
        c_debt = float(cust.get("total_debt") or 0)
        tg_id = cust.get("telegram_id")
        
        shops_data[shop_id]["total_debt"] += c_debt
        shops_data[shop_id]["customers"].append(cust)
        
        # 3 kundan beri to'lamaganlikni hisoblash (Mijozning oxirgi to'lov yoki yangi qarz sanasiga asosan):
        # Agar mijoz oxirgi 3 kunda pul to'lagan bo'lsa YOKI yangi qarz olgan bo'lsa (bugun, kecha, o'tgan kun),
        # u faol hisoblanadi va 3 kundan beri to'lamaganlarga TUSHMASLIGI kerak!
        last_pay = cust.get("last_payment_date")
        lp_dt = None
        if last_pay:
            try:
                lp_dt = datetime.fromisoformat(str(last_pay).replace("Z", "+00:00")).date()
            except Exception:
                try:
                    lp_dt = date.fromisoformat(str(last_pay)[:10])
                except Exception:
                    lp_dt = None

        # Oxirgi olingan qarz sanasi
        latest_debt_dt = None
        for d in cust.get("debts", []):
            dd = d.get("debt_date") or d.get("created_at")
            if dd:
                try:
                    parsed_dd = date.fromisoformat(str(dd)[:10])
                    if latest_debt_dt is None or parsed_dd > latest_debt_dt:
                        latest_debt_dt = parsed_dd
                except Exception:
                    pass

        # Eng so'nggi amal sanasi (to'lov yoki yangi qarz)
        last_activity_date = None
        if lp_dt and latest_debt_dt:
            last_activity_date = max(lp_dt, latest_debt_dt)
        elif lp_dt:
            last_activity_date = lp_dt
        elif latest_debt_dt:
            last_activity_date = latest_debt_dt

        days_without_activity = (today_dt - last_activity_date).days if last_activity_date else 0
        is_3days = (days_without_activity >= 3 and c_debt > 0)
        cust["is_3days_overdue"] = is_3days
        cust["max_days_overdue"] = max(days_without_activity, 0)

        if is_3days:
            shops_data[shop_id]["overdue_3days"].append({
                "name": c_name,
                "phone": c_phone,
                "debt": c_debt,
                "days_overdue": cust["max_days_overdue"],
                "customer_id": cust["customer_id"],
                "telegram_id": tg_id,
                "cust_obj": cust
            })

    # Agar umuman qarzdor bo'lmasa, default shop uchun hisobot tayyorlash
    if not shops_data:
        shops_data["5832B1F2"] = {
            "shop_name": "Do'kon",
            "total_debt": 0.0,
            "customers": [],
            "overdue_3days": [],
            "sent": [],
            "skipped_2day": [],
            "unlinked": [],
            "failed": []
        }

    # 3. SMS yuborish va hisobot tayyorlash
    total_sent = 0
    total_skipped = 0
    total_unlinked = 0
    total_failed = 0
    total_overdue_all_shops = 0
    
    for shop_id, sdata in shops_data.items():
        overdue_3days = sdata["overdue_3days"]
        total_overdue_count = len(overdue_3days)
        total_overdue_all_shops += total_overdue_count
        
        # 3 kundan beri to'lamagan mijozlarga SMS yuborish
        for c_item in overdue_3days:
            cust = c_item["cust_obj"]
            c_name = c_item["name"]
            c_phone = c_item["phone"]
            c_debt = c_item["debt"]
            tg_id = c_item["telegram_id"]
            days_overdue = c_item["days_overdue"]
            
            # Telegram ID yo'q bo'lsa -> SMS bormadi (botga ulanmagan)
            if not tg_id:
                sdata["unlinked"].append({
                    "name": c_name,
                    "phone": c_phone,
                    "debt": c_debt,
                    "days_overdue": days_overdue,
                    "reason": "Botga kirmagan / ulanmagan"
                })
                continue
                
            # 2 kunda bir marta vs har kuni qoidasini tekshirish
            should_send, reason = await should_send_sms_to_customer(
                customer_id=cust["customer_id"],
                total_overdue_count=total_overdue_count,
                is_manual=(manual_admin_id is not None)
            )
            
            if not should_send:
                sdata["skipped_2day"].append({
                    "name": c_name,
                    "phone": c_phone,
                    "debt": c_debt,
                    "days_overdue": days_overdue,
                    "reason": reason
                })
                continue
                
            # SMS yuborish
            text = build_daily_reminder_text(cust, days_overdue=days_overdue)
            base_url = settings.MINI_APP_URL or "https://dokon-hisobi.onrender.com"
            web_app_url = f"{base_url}?role=customer&customer_id={cust['customer_id']}&v=2.5"
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
                sdata["sent"].append({
                    "name": c_name,
                    "phone": c_phone,
                    "debt": c_debt,
                    "days_overdue": days_overdue,
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
                    
                sdata["failed"].append({
                    "name": c_name,
                    "phone": c_phone,
                    "debt": c_debt,
                    "days_overdue": days_overdue,
                    "tg_id": tg_id,
                    "reason": reason
                })
                for d in cust.get("debts", []):
                    await log_notification(d["debt_id"], cust["customer_id"], "daily_19pm", False, err_str)
                logger.warning(f"❌ 19:00 eslatma yuborilmadi ({c_name}): {ex}")

        total_sent += len(sdata["sent"])
        total_skipped += len(sdata["skipped_2day"])
        total_unlinked += len(sdata["unlinked"])
        total_failed += len(sdata["failed"])
        
        # Har bir do'kon adminlariga to'liq hisobotni yuborish
        admin_ids = await get_shop_admin_ids(shop_id, manual_admin_id)
        report_messages = build_admin_summary_messages(
            shop_name=sdata["shop_name"],
            total_count=len(sdata["customers"]),
            total_amount=sdata["total_debt"],
            overdue_3days_list=sdata["overdue_3days"],
            sent_list=sdata["sent"],
            skipped_list=sdata["skipped_2day"],
            unlinked_list=sdata["unlinked"],
            failed_list=sdata["failed"]
        )
        
        for aid in admin_ids:
            for r_msg in report_messages:
                try:
                    await bot.send_message(chat_id=aid, text=r_msg, parse_mode="HTML")
                except Exception as aex:
                    logger.warning(f"⚠️ Admin ({aid}) ga hisobot yuborilmadi: {aex}")
                    
    logger.info(
        f"⏰ 19:00 eslatmalar yakunlandi: Jami: {len(customers)}, 3 kundan beri to'lamagan: {total_overdue_all_shops}, "
        f"Yuborildi: {total_sent}, 2 kunda bir oraliq: {total_skipped}, Botga ulanmagan: {total_unlinked}, Xato: {total_failed}"
    )
    return {
        "total": len(customers),
        "overdue_3days": total_overdue_all_shops,
        "sent": total_sent,
        "skipped_2day": total_skipped,
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

async def _delayed_initial_check(bot):
    await asyncio.sleep(15)
    try:
        logger.info("🚀 Dastlabki 3 kundan beri to'lamaganlarni tekshirish va eslatmalar...")
        await send_reminders(bot)
    except Exception as e:
        logger.error(f"Dastlabki eslatmalar xatosi: {e}")

def setup_scheduler(bot) -> AsyncIOScheduler:
    """Scheduler yaratish va ishga sozlash"""
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    
    # 1. Har kuni ertalab soat 10:00 da
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(hour=10, minute=0, timezone="Asia/Tashkent"),
        args=[bot],
        id="daily_reminders_10am",
        name="Har kuni 10:00 qarz eslatmalari va Admin hisoboti",
        replace_existing=True,
        misfire_grace_time=7200
    )

    # 2. Har kuni kechqurun soat 19:00 da
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(hour=19, minute=0, timezone="Asia/Tashkent"),
        args=[bot],
        id="daily_reminders_19pm",
        name="Har kuni 19:00 qarz eslatmalari va Admin hisoboti",
        replace_existing=True,
        misfire_grace_time=7200
    )
    
    # 3. Har 5 daqiqada Render Free uxlab qolmasligi uchun keep-alive
    scheduler.add_job(
        keep_alive_ping,
        trigger="interval",
        minutes=5,
        id="render_keep_alive",
        name="Render Keep Alive Ping",
        replace_existing=True
    )

    # 4. Bot ishga tushganda ham darhol tekshirish
    try:
        asyncio.create_task(_delayed_initial_check(bot))
    except Exception:
        pass
    
    return scheduler
