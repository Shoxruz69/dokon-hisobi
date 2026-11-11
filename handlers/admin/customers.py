from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.queries import (
    get_admin_by_telegram_id,
    get_customers_list,
    get_customer_detail
)
from keyboards.admin_kb import get_customer_actions_kb, get_debt_actions_kb
from utils.validators import format_amount, format_date_uz
from utils.formatters import esc, build_customer_detail_text

router = Router()

class SearchCustomerFSM(StatesGroup):
    waiting_for_query = State()

@router.message(Command("customers"))
@router.message(F.text == "👥 Mijozlar")
@router.callback_query(F.data == "customers_list")
async def show_customers_list(event: Message | CallbackQuery, admin: dict = None):
    user_id = event.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if not admin:
        msg = "🚫 Siz do'kon ma'muri emassiz."
        if isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return
        
    customers = await get_customers_list(admin["shop_id"])
    
    if not customers:
        text = (
            "👥 <b>Mijozlar ro'yxati bo'sh</b>\n\n"
            "Siz hali birorta ham qarzdor mijoz qo'shmadingiz.\n"
            "Yangi mijoz qo'shish uchun quyidagi tugmani bosing:"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Mijoz qo'shish", callback_data="add_customer")]
        ])
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    text = f"👥 <b>Mijozlar ro'yxati ({len(customers)} ta):</b>\n\n"
    buttons = []
    
    for c in customers[:20]:  # Telegram cheklovi sabab 20 tagacha
        has_overdue = c.get("overdue_debts", 0) > 0
        total_debt = c.get("total_debt", 0)
        
        status_icon = "🔴" if has_overdue else ("🟡" if total_debt > 0 else "✅")
        btn_text = f"{status_icon} {c['full_name']} — {format_amount(total_debt)}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"cust_{c['id']}")])
        
    buttons.append([
        InlineKeyboardButton(text="🔍 Qidirish", callback_data="search_customer"),
        InlineKeyboardButton(text="➕ Yangi mijoz", callback_data="add_customer")
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("cust_"))
async def view_customer_card(callback: CallbackQuery, admin: dict = None):
    customer_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if not admin:
        await callback.answer("🚫 Ruxsat berilmagan", show_alert=True)
        return
        
    data = await get_customer_detail(customer_id, admin["shop_id"])
    if not data:
        await callback.answer("❌ Mijoz topilmadi yoki boshqa do'konga tegishli!", show_alert=True)
        return
        
    text = build_customer_detail_text(data, data.get("debts", []))
    kb = get_customer_actions_kb(customer_id)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("view_debts_"))
async def view_customer_debts_management(callback: CallbackQuery, admin: dict = None):
    customer_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if not admin:
        await callback.answer("🚫 Ruxsat yo'q", show_alert=True)
        return
        
    data = await get_customer_detail(customer_id, admin["shop_id"])
    if not data:
        await callback.answer("❌ Mijoz topilmadi", show_alert=True)
        return
        
    debts = data.get("debts", [])
    if not debts:
        await callback.answer("Ushbu mijozda qarzlar yo'q.", show_alert=True)
        return
        
    await callback.message.delete()
    
    for d in debts:
        is_paid = d.get("status") == "paid"
        status_text = "✅ To'langan" if is_paid else ("🔴 Muddati o'tgan" if d.get("status") == "overdue" else "🟡 Faol")
        card = (
            f"📦 <b>Qarz: {esc(d['description'])}</b>\n"
            f"💰 Summa: <b>{format_amount(d['amount'])}</b>\n"
            f"📅 Olingan sana: {format_date_uz(d['debt_date'])}\n"
            f"⏰ To'lov muddati: <b>{format_date_uz(d['due_date'])}</b>\n"
            f"📌 Holat: <i>{status_text}</i>"
        )
        kb = get_debt_actions_kb(d["id"], customer_id, is_paid=is_paid)
        await callback.message.answer(card, parse_mode="HTML", reply_markup=kb)

# ============================================================
# QIDIRISH
# ============================================================

@router.callback_query(F.data == "search_customer")
async def start_search_customer(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 <b>Mijozni qidirish</b>\n\n"
        "Mijozning ismi yoki telefon raqamini kiriting:\n"
        "<i>Misol: Bobur yoki 901234567</i>",
        parse_mode="HTML"
    )
    await state.set_state(SearchCustomerFSM.waiting_for_query)

@router.message(SearchCustomerFSM.waiting_for_query)
async def process_search_query(message: Message, state: FSMContext, admin: dict = None):
    user_id = message.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if not admin:
        await message.answer("🚫 Siz do'kon ma'muri emassiz.")
        await state.clear()
        return
        
    query = message.text.strip()
    customers = await get_customers_list(admin["shop_id"], search=query)
    await state.clear()
    
    if not customers:
        await message.answer(
            f"🔍 <code>{esc(query)}</code> bo'yicha hech qanday mijoz topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Qayta qidirish", callback_data="search_customer")],
                [InlineKeyboardButton(text="👥 Barcha mijozlar", callback_data="customers_list")]
            ])
        )
        return
        
    buttons = []
    for c in customers[:15]:
        total_debt = c.get("total_debt", 0)
        btn_text = f"👤 {c['full_name']} — {format_amount(total_debt)}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"cust_{c['id']}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Barcha mijozlar", callback_data="customers_list")])
    
    await message.answer(
        f"🔍 <b>Qidiruv natijalari ({len(customers)} ta):</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

