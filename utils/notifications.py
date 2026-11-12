import aiohttp
import logging
from typing import Optional
from config import settings
from utils.validators import format_amount, format_date_uz
from utils.formatters import esc

logger = logging.getLogger(__name__)

async def send_telegram_notification(telegram_id: Optional[int], message_html: str) -> bool:
    """Mijozga Telegram orqali xabarnoma (SMS) yuborish"""
    if not telegram_id:
        logger.info("ℹ️ Mijozda Telegram ID bog'lanmagan (xabar yuborilmadi)")
        return False

    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": telegram_id,
        "text": message_html,
        "parse_mode": "HTML"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    logger.info(f"✅ Telegram xabarnomasi muvaffaqiyatli yuborildi: {telegram_id}")
                    return True
                else:
                    body = await resp.text()
                    logger.warning(f"⚠️ Telegram xabarnoma yuborilmadi ({resp.status}): {body}")
                    return False
    except Exception as e:
        logger.warning(f"⚠️ Telegram xabarnoma yuborishda xatolik: {e}")
        return False

async def notify_customer_debt_added(
    customer: dict,
    shop_name: str,
    amount: float,
    description: str,
    due_date: str,
    total_debt: float
) -> bool:
    """Mijozga yangi qarz qo'shilganligi haqida Telegram SMS yuborish"""
    tg_id = customer.get("telegram_id")
    if not tg_id:
        return False

    msg = (
        f"Assalomu alaykum, <b>{esc(customer.get('full_name', 'Mijoz'))}</b>! 👋\n\n"
        f"🏪 <b>{esc(shop_name)}</b> do'konidan sizga yangi qarz yozildi:\n\n"
        f"📦 <b>Nima olingan:</b> {esc(description)}\n"
        f"➕ <b>Qo'shilgan summa:</b> <b>{format_amount(amount)}</b>\n"
        f"⏰ <b>To'lash muddati:</b> <b>{format_date_uz(due_date)}</b>\n\n"
        f"💳 <b>Jami qarzingiz:</b> <b>{format_amount(total_debt)}</b>\n\n"
        f"<i>Batafsil ma'lumotni bot menyusi orqali ko'rishingiz mumkin.</i>"
    )
    return await send_telegram_notification(tg_id, msg)

async def notify_customer_partial_payment(
    customer: dict,
    shop_name: str,
    paid_amount: float,
    remaining_debt: float
) -> bool:
    """Qarz qisman yoki to'liq to'langanda qancha to'langan va qancha qolganligi haqida Telegram SMS"""
    tg_id = customer.get("telegram_id")
    if not tg_id:
        return False

    if remaining_debt > 0:
        msg = (
            f"Assalomu alaykum, <b>{esc(customer.get('full_name', 'Mijoz'))}</b>! 👋\n\n"
            f"🏪 <b>{esc(shop_name)}</b> do'koniga to'lov qabul qilindi:\n\n"
            f"✅ <b>To'langan summa:</b> <b>{format_amount(paid_amount)}</b>\n"
            f"💰 <b>Qolgan qarzingiz:</b> <b>{format_amount(remaining_debt)}</b>\n\n"
            f"To'lovingiz uchun katta rahmat!"
        )
    else:
        msg = (
            f"Assalomu alaykum, <b>{esc(customer.get('full_name', 'Mijoz'))}</b>! 👋\n\n"
            f"🏪 <b>{esc(shop_name)}</b> do'konidagi barcha qarzlaringiz to'liq to'landi! ✅\n\n"
            f"✅ <b>Oxirgi to'lov:</b> <b>{format_amount(paid_amount)}</b>\n"
            f"🎉 <b>Qarzingiz qolmadi:</b> <b>0 so'm</b>\n\n"
            f"Do'konimizdan xarid qilganingiz uchun rahmat!"
        )

    return await send_telegram_notification(tg_id, msg)

async def notify_customer_debt_paid(
    customer: dict,
    shop_name: str,
    debt_amount: float,
    description: str,
    remaining_debt: float
) -> bool:
    """Bitta qarz to'liq yopilganda yuboriladigan Telegram SMS"""
    tg_id = customer.get("telegram_id")
    if not tg_id:
        return False

    if remaining_debt > 0:
        msg = (
            f"Assalomu alaykum, <b>{esc(customer.get('full_name', 'Mijoz'))}</b>! 👋\n\n"
            f"🏪 <b>{esc(shop_name)}</b> do'konidagi quyidagi qarzingiz to'landi: ✅\n\n"
            f"📦 <b>Mahsulot:</b> {esc(description)}\n"
            f"✅ <b>To'langan summa:</b> <b>{format_amount(debt_amount)}</b>\n\n"
            f"💰 <b>Qolgan jami qarzingiz:</b> <b>{format_amount(remaining_debt)}</b>\n\n"
            f"To'lovingiz uchun katta rahmat!"
        )
    else:
        msg = (
            f"Assalomu alaykum, <b>{esc(customer.get('full_name', 'Mijoz'))}</b>! 👋\n\n"
            f"🏪 <b>{esc(shop_name)}</b> do'konidagi barcha qarzlaringiz to'liq to'landi! 🎉\n\n"
            f"📦 <b>Mahsulot:</b> {esc(description)}\n"
            f"✅ <b>To'langan summa:</b> <b>{format_amount(debt_amount)}</b>\n"
            f"💰 <b>Qolgan qarzingiz:</b> <b>0 so'm</b>\n\n"
            f"To'lovingiz uchun katta rahmat!"
        )

    return await send_telegram_notification(tg_id, msg)

