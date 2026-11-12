import html
from typing import List, Dict, Any
from .validators import format_amount, format_date_uz

def esc(text: Any) -> str:
    """HTML belgilarini xavfsiz qilish"""
    if text is None:
        return ""
    return html.escape(str(text))

def build_admin_stats_text(stats: dict, shop_name: str) -> str:
    """Admin uchun chiroyli statistika matni"""
    total_debt = format_amount(stats.get("total_debt_sum", 0))
    month_paid = format_amount(stats.get("month_paid_sum", 0))
    
    return (
        f"📊 <b>{esc(shop_name)} — Qarzlar statistikasi</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💸 <b>Jami faol qarz:</b> {total_debt}\n"
        f"✅ <b>Oxirgi 30 kunda to'landi:</b> {month_paid}\n\n"
        f"👥 <b>Jami mijozlar:</b> {stats.get('total_customers', 0)} ta\n"
        f"🟡 <b>Faol qarzlar soni:</b> {stats.get('active_debts', 0)} ta\n"
        f"🔴 <b>Muddati o'tgan qarzlar:</b> {stats.get('overdue_debts', 0)} ta\n"
        f"📅 <b>Bu hafta to'lanishi kerak:</b> {stats.get('due_this_week', 0)} ta\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Mijozlar ro'yxatini ko'rish yoki yangi qarz qo'shish uchun menyudan foydalaning.</i>"
    )

def build_customer_detail_text(customer: dict, debts: List[dict]) -> str:
    """Admin uchun mijoz to'liq kartochkasi"""
    total_debt = format_amount(customer.get("total_debt", 0))
    has_tg = "✅ Ulangan" if customer.get("telegram_id") else "❌ Ulanmagan"
    notes = customer.get("notes") or "Izoh yo'q"
    
    text = (
        f"👤 <b>Mijoz:</b> {esc(customer['full_name'])}\n"
        f"📱 <b>Telefon:</b> <code>{esc(customer['phone'])}</code>\n"
        f"💬 <b>Telegram:</b> {has_tg}\n"
        f"📝 <b>Izoh:</b> {esc(notes)}\n"
        f"💸 <b>Jami qarz:</b> <b>{total_debt}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Qarzlar ro'yxati:</b>\n\n"
    )
    
    if not debts:
        text += "🎉 <i>Ushbu mijozda hozircha qarz mavjud emas.</i>\n"
        return text
    
    for i, d in enumerate(debts, 1):
        status = d.get("status")
        if status == "paid":
            badge = "✅ To'langan"
        elif status == "overdue":
            badge = "🔴 Muddati o'tgan"
        else:
            badge = "🟡 Faol"
            
        text += (
            f"<b>#{i} — {esc(d['description'])}</b>\n"
            f"   💰 Summa: <b>{format_amount(d['amount'])}</b>\n"
            f"   📅 Olingan: {format_date_uz(d.get('debt_date', ''))}\n"
            f"   ⏰ Muddat: <b>{format_date_uz(d.get('due_date', ''))}</b>\n"
            f"   📌 Holat: <i>{badge}</i>\n"
        )
        if status == "paid" and d.get("paid_date"):
            text += f"   💳 To'langan sana: {format_date_uz(d['paid_date'])}\n"
        text += "\n"
        
    return text

def build_customer_debts_view(customer: dict, debts: List[dict]) -> str:
    """Mijozning o'zi ko'radigan qarzlar hisoboti"""
    active_debts = [d for d in debts if d.get("status") in ("active", "overdue")]
    total = sum(d["amount"] for d in active_debts)

    if not active_debts or total <= 0:
        return (
            f"🎉 Salom, <b>{esc(customer['full_name'])}</b>!\n\n"
            f"🏪 Do'kon: <b>{esc(customer.get('shop_name', 'Do\'kon'))}</b>\n\n"
            f"✅ <b>Tabriklaymiz, sizda hech qanday to'lanmagan qarz yo'q!</b>\n"
            f"Barcha to'lovlar to'liq amalga oshirilgan.\n\n"
            f"Hisob-kitoblar tarixini ko'rish uchun pastdagi <b>Shaxsiy hisob (Mini App)</b> tugmasini bosing:"
        )
    
    text = (
        f"👤 Salom, <b>{esc(customer['full_name'])}</b>! 👋\n"
        f"🏪 Do'kon: <b>{esc(customer.get('shop_name', 'Do\'kon'))}</b>\n\n"
        f"💳 <b>Sizning qarzlaringiz:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    for i, debt in enumerate(debts, 1):
        is_overdue = debt.get("status") == "overdue"
        icon = "🔴" if is_overdue else "🟡"
        status_note = "\n   ⚠️ <i>To'lov muddati o'tib ketgan!</i>" if is_overdue else ""
        
        text += (
            f"{icon} <b>#{i} — {esc(debt['description'])}</b>\n"
            f"   💰 {format_amount(debt['amount'])}\n"
            f"   📅 To'lov muddati: <b>{format_date_uz(debt['due_date'])}</b>"
            f"{status_note}\n\n"
        )
        
    text += (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 <b>Jami to'lanishi kerak: {format_amount(total)}</b>\n\n"
        f"📞 Do'kon bilan bog'lanish: <code>{esc(customer.get('shop_phone') or 'Bog\'lanish raqami belgilanmagan')}</code>"
    )
    return text

