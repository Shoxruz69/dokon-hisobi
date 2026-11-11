from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command

from database.queries import (
    get_customer_by_telegram_id,
    get_customer_active_debts
)
from keyboards.customer_kb import get_customer_main_kb, get_phone_request_kb, get_customer_inline_kb
from utils.formatters import esc, build_customer_debts_view

router = Router()

@router.message(Command("mydebts"))
@router.message(F.text.contains("Mening qarzlarim"))
@router.message(F.text.contains("Yangilash"))
@router.callback_query(F.data == "my_debts_refresh")
async def show_my_debts(event: Message | CallbackQuery):
    user_id = event.from_user.id
    customers = await get_customer_by_telegram_id(user_id)
    
    if not customers:
        text = (
            "👤 <b>Siz hali telefon raqamingizni tasdiqlamadingiz.</b>\n\n"
            "Qarzlaringizni ko'rish uchun telefon raqamingizni yuboring:"
        )
        if isinstance(event, CallbackQuery):
            await event.message.answer(text, parse_mode="HTML", reply_markup=get_phone_request_kb())
            await event.answer()
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=get_phone_request_kb())
        return

    if isinstance(event, CallbackQuery):
        await event.answer("🔄 Yangilandi!")
        
    for cust in customers:
        debts = await get_customer_active_debts(cust["id"])
        view_text = build_customer_debts_view(cust, debts)
        if isinstance(event, CallbackQuery):
            await event.message.answer(view_text, parse_mode="HTML", reply_markup=get_customer_inline_kb())
        else:
            await event.answer(view_text, parse_mode="HTML", reply_markup=get_customer_inline_kb())

@router.message(F.text.contains("bog'lanish") | F.text.contains("boglanish"))
async def contact_shop(message: Message):
    user_id = message.from_user.id
    customers = await get_customer_by_telegram_id(user_id)
    
    if not customers:
        await message.answer("Siz do'kon tizimiga ulanmagansiz.")
        return
        
    text = "📞 <b>Do'konlar aloqa ma'lumotlari:</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    for c in customers:
        phone = c.get("shop_phone") or "Telefon kiritilmagan"
        text += (
            f"🏪 <b>{esc(c['shop_name'])}</b>\n"
            f"📱 Telefon: <code>{esc(phone)}</code>\n\n"
        )
    await message.answer(text, parse_mode="HTML")

