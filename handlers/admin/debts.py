from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.queries import (
    get_admin_by_telegram_id,
    add_customer,
    mark_debt_paid,
    delete_debt,
    get_customer_detail
)
from utils.validators import (
    validate_full_name,
    validate_phone,
    validate_amount,
    validate_date,
    format_amount,
    format_date_uz
)
from utils.formatters import esc

router = Router()

class AddDebtFSM(StatesGroup):
    full_name = State()
    phone = State()
    amount = State()
    description = State()
    due_date = State()
    confirm = State()

class AddDebtToExistingFSM(StatesGroup):
    customer_id = State()
    amount = State()
    description = State()
    due_date = State()
    confirm = State()

# ============================================================
# YANGI MIJOZ VA QARZ QO'SHISH
# ============================================================

@router.message(Command("add"))
@router.message(F.text == "➕ Yangi qarz")
@router.callback_query(F.data == "add_customer")
async def start_add_debt_flow(event: Message | CallbackQuery, state: FSMContext, admin: dict = None):
    user_id = event.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if not admin:
        msg = "🚫 Siz admin emassiz."
        if isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return
        
    text = (
        "➕ <b>Yangi mijoz va qarz qo'shish</b>\n\n"
        "1️⃣ Mijozning <b>Ism Familiyasini</b> kiriting:\n"
        "<i>Misol: Aliyev Bobur Erkinovich</i>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML")
    else:
        await event.answer(text, parse_mode="HTML")
        
    await state.set_state(AddDebtFSM.full_name)

@router.message(AddDebtFSM.full_name)
async def process_full_name(message: Message, state: FSMContext):
    is_valid, result = validate_full_name(message.text)
    if not is_valid:
        await message.answer(result)
        return
        
    await state.update_data(full_name=result)
    await message.answer(
        f"✅ Ism: <b>{esc(result)}</b>\n\n"
        "2️⃣ Mijozning <b>telefon raqamini</b> kiriting:\n"
        "<i>Misol: +998901234567 yoki 901234567</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddDebtFSM.phone)

@router.message(AddDebtFSM.phone)
async def process_phone(message: Message, state: FSMContext):
    is_valid, result = validate_phone(message.text)
    if not is_valid:
        await message.answer(result)
        return
        
    await state.update_data(phone=result)
    await message.answer(
        f"✅ Telefon: <code>{esc(result)}</code>\n\n"
        "3️⃣ <b>Qarz summasini</b> kiriting (so'mda):\n"
        "<i>Misol: 150000 yoki 1 500 000</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddDebtFSM.amount)

@router.message(AddDebtFSM.amount)
async def process_amount(message: Message, state: FSMContext):
    is_valid, result = validate_amount(message.text)
    if not is_valid:
        await message.answer(result)
        return
        
    await state.update_data(amount=result)
    await message.answer(
        f"✅ Summa: <b>{format_amount(result)}</b>\n\n"
        "4️⃣ Mijoz <b>nima olganini</b> yozing:\n"
        "<i>Misol: Un 10kg, Yog' 2 litr, Shakar 5kg</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddDebtFSM.description)

@router.message(AddDebtFSM.description)
async def process_description(message: Message, state: FSMContext):
    desc = message.text.strip() if message.text else ""
    if len(desc) < 2:
        await message.answer("❌ Nima olganini aniqroq yozing (kamida 2 harf):")
        return
        
    await state.update_data(description=desc)
    await message.answer(
        f"✅ Olgan narsa: <b>{esc(desc)}</b>\n\n"
        "5️⃣ <b>To'lov sanasini</b> kiriting (kun.oy.yil):\n"
        "<i>Misol: 25.11.2026 yoki 2026-11-25</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddDebtFSM.due_date)

@router.message(AddDebtFSM.due_date)
async def process_due_date(message: Message, state: FSMContext):
    is_valid, result = validate_date(message.text)
    if not is_valid:
        await message.answer(result)
        return
        
    await state.update_data(due_date=result)
    data = await state.get_data()
    
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash va Saqlash", callback_data="confirm_add_debt"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_debt_action")
        ]
    ])
    
    text = (
        "📋 <b>Ma'lumotlarni tekshiring:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mijoz:</b> {esc(data['full_name'])}\n"
        f"📱 <b>Telefon:</b> <code>{esc(data['phone'])}</code>\n"
        f"💰 <b>Qarz summasi:</b> <b>{format_amount(data['amount'])}</b>\n"
        f"📦 <b>Nima oldi:</b> {esc(data['description'])}\n"
        f"📅 <b>To'lov sanasi:</b> <b>{format_date_uz(data['due_date'])}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Barcha ma'lumotlar to'g'rimi?"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=confirm_kb)
    await state.set_state(AddDebtFSM.confirm)

@router.callback_query(F.data == "confirm_add_debt", AddDebtFSM.confirm)
async def confirm_add_debt(callback: CallbackQuery, state: FSMContext, admin: dict = None):
    data = await state.get_data()
    user_id = callback.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if not admin:
        await callback.answer("🚫 Siz admin emassiz!", show_alert=True)
        return
        
    result = await add_customer(
        shop_id=admin["shop_id"],
        full_name=data["full_name"],
        phone=data["phone"],
        amount=data["amount"],
        description=data["description"],
        due_date=data["due_date"]
    )
    await state.clear()
    
    is_new = result.get("is_new", True)
    status_text = "🎉 Yangi mijoz va qarz muvaffaqiyatli saqlandi!" if is_new else "✅ Mavjud mijoz hisobiga yangi qarz qo'shildi!"
    
    await callback.message.edit_text(
        f"{status_text}\n\n"
        f"👤 <b>Mijoz:</b> {esc(data['full_name'])}\n"
        f"📱 <b>Telefon:</b> <code>{esc(data['phone'])}</code>\n"
        f"💰 <b>Summa:</b> {format_amount(data['amount'])}\n"
        f"📅 <b>To'lov muddati:</b> {format_date_uz(data['due_date'])}\n\n"
        f"💡 <i>Mijoz botga kirib telefon raqamini tasdiqlasa, unga avtomatik eslatmalar boradi.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Mijozlar ro'yxatiga", callback_data="customers_list")],
            [InlineKeyboardButton(text="➕ Yana qarz qo'shish", callback_data="add_customer")]
        ])
    )

# ============================================================
# MAVJUD MIJOZGA QARZ QO'SHISH
# ============================================================

@router.callback_query(F.data.startswith("add_debt_to_"))
async def start_add_debt_to_existing(callback: CallbackQuery, state: FSMContext, admin: dict = None):
    customer_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
    if not admin:
        await callback.answer("🚫 Ruxsat yo'q", show_alert=True)
        return
        
    cust = await get_customer_detail(customer_id, admin["shop_id"])
    if not cust:
        await callback.answer("Mijoz topilmadi", show_alert=True)
        return
        
    await state.update_data(
        customer_id=customer_id,
        full_name=cust["full_name"],
        phone=cust["phone"]
    )
    
    await callback.message.edit_text(
        f"➕ <b>{esc(cust['full_name'])}</b> ga yangi qarz qo'shish:\n\n"
        "💰 <b>Qarz summasini</b> kiriting (so'mda):\n"
        "<i>Misol: 75000</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddDebtToExistingFSM.amount)

@router.message(AddDebtToExistingFSM.amount)
async def process_existing_amount(message: Message, state: FSMContext):
    is_valid, result = validate_amount(message.text)
    if not is_valid:
        await message.answer(result)
        return
    await state.update_data(amount=result)
    await message.answer(
        f"✅ Summa: <b>{format_amount(result)}</b>\n\n"
        "📦 Mijoz <b>nima olganini</b> yozing:\n"
        "<i>Misol: Go'sht 2kg</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddDebtToExistingFSM.description)

@router.message(AddDebtToExistingFSM.description)
async def process_existing_desc(message: Message, state: FSMContext):
    desc = message.text.strip() if message.text else ""
    if len(desc) < 2:
        await message.answer("❌ Nima olganini aniqroq yozing:")
        return
    await state.update_data(description=desc)
    await message.answer(
        f"✅ Narsa: <b>{esc(desc)}</b>\n\n"
        "📅 <b>To'lov sanasini</b> kiriting (kun.oy.yil):\n"
        "<i>Misol: 30.11.2026</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddDebtToExistingFSM.due_date)

@router.message(AddDebtToExistingFSM.due_date)
async def process_existing_due_date(message: Message, state: FSMContext):
    is_valid, result = validate_date(message.text)
    if not is_valid:
        await message.answer(result)
        return
    await state.update_data(due_date=result)
    data = await state.get_data()
    
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_existing_debt"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_debt_action")
        ]
    ])
    
    text = (
        f"📋 <b>{esc(data['full_name'])} ga qarz qo'shish:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Summa:</b> <b>{format_amount(data['amount'])}</b>\n"
        f"📦 <b>Narsa:</b> {esc(data['description'])}\n"
        f"📅 <b>Muddati:</b> <b>{format_date_uz(data['due_date'])}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Tasdiqlaysizmi?"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=confirm_kb)
    await state.set_state(AddDebtToExistingFSM.confirm)

@router.callback_query(F.data == "confirm_existing_debt", AddDebtToExistingFSM.confirm)
async def confirm_existing_debt(callback: CallbackQuery, state: FSMContext, admin: dict = None):
    data = await state.get_data()
    user_id = callback.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    await add_customer(
        shop_id=admin["shop_id"],
        full_name=data["full_name"],
        phone=data["phone"],
        amount=data["amount"],
        description=data["description"],
        due_date=data["due_date"]
    )
    customer_id = data["customer_id"]
    await state.clear()
    
    await callback.message.edit_text(
        f"✅ <b>Qarz muvaffaqiyatli qo'shildi!</b>\n\n"
        f"👤 {esc(data['full_name'])}\n"
        f"💰 {format_amount(data['amount'])}\n"
        f"📅 To'lov: {format_date_uz(data['due_date'])}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Mijoz kartochkasiga", callback_data=f"cust_{customer_id}")]
        ])
    )

# ============================================================
# TO'LOV VA O'CHIRISH
# ============================================================

@router.callback_query(F.data.startswith("pay_debt_"))
async def process_pay_debt(callback: CallbackQuery, admin: dict = None):
    debt_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if not admin:
        await callback.answer("🚫 Ruxsat yo'q", show_alert=True)
        return
        
    success = await mark_debt_paid(debt_id, admin["shop_id"], user_id)
    if success:
        await callback.answer("✅ Qarz to'landi deb belgilandi!", show_alert=True)
        await callback.message.edit_text(
            f"✅ <b>Qarz to'landi deb belgilandi!</b>\n"
            f"Tizimda to'lov tarixi qayd etildi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Mijozlar ro'yxati", callback_data="customers_list")]
            ])
        )
    else:
        await callback.answer("❌ Qarz topilmadi yoki allaqachon to'langan", show_alert=True)

@router.callback_query(F.data.startswith("del_debt_"))
async def process_delete_debt(callback: CallbackQuery, admin: dict = None):
    debt_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if not admin:
        await callback.answer("🚫 Ruxsat yo'q", show_alert=True)
        return
        
    success = await delete_debt(debt_id, admin["shop_id"])
    if success:
        await callback.answer("🗑 Qarz o'chirildi!", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer("❌ O'chirib bo'lmadi", show_alert=True)

@router.callback_query(F.data == "cancel_debt_action")
async def cancel_debt_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")

