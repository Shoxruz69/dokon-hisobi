from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from config import settings
from database.db import db_execute
from database.queries import (
    get_admin_by_telegram_id,
    get_first_active_admin,
    update_admin_profile,
    update_admin_shop_name,
    get_customer_by_telegram_id,
    get_all_customers_by_phone,
    link_customer_telegram,
    get_customer_active_debts
)
from keyboards.admin_kb import get_admin_main_inline_kb, get_admin_reply_kb
from keyboards.customer_kb import get_phone_request_kb, get_customer_main_kb
from utils.validators import validate_phone, format_amount, format_date_uz
from utils.formatters import esc

router = Router()

class AdminSetup(StatesGroup):
    waiting_for_shop_name = State()
    waiting_for_full_name = State()
    waiting_for_phone = State()

class AdminEditShop(StatesGroup):
    waiting_for_new_name = State()

class CustomerVerification(StatesGroup):
    waiting_for_phone = State()

def get_customer_webapp_kb(customer_id: int) -> InlineKeyboardMarkup:
    """Mijoz uchun o'z qarzlarini ko'rsatuvchi Mini App tugmasi"""
    url = f"{settings.MINI_APP_URL}?role=customer&customer_id={customer_id}&v=2.2"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Mening qarzlarim (Mini App)", web_app=WebAppInfo(url=url))]
    ])

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, admin: dict = None):
    await state.clear()
    user_id = message.from_user.id
    
    is_env_admin = settings.is_admin_id(user_id)

    # 1. ADMIN TEKSHIRUVI
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)

    # Agar telegram_id bo'yicha topilmasa, lekin tizim egasi bo'lsa yoki bazada mavjud do'kon bo'lsa
    if not admin and is_env_admin:
        admin = await get_first_active_admin()
        if admin and admin.get("telegram_id") != user_id:
            try:
                await db_execute("UPDATE admins SET telegram_id = ? WHERE id = ?", user_id, admin["id"])
                admin["telegram_id"] = user_id
            except Exception:
                pass

    # Agar foydalanuvchi tizim administratori bo'lsa yoki admin topilsa
    if is_env_admin or admin:
        # Agar bazada allaqachon do'kon yaratilgan bo'lsa -> HECH QACHON qayta ro'yxatdan o'tishni so'ramaymiz!
        if admin and admin.get("shop_name"):
            shop_name = admin.get("shop_name", "Do'kon")
            shop_id = admin.get("shop_id", "")
            admin_name = admin.get("full_name") or message.from_user.full_name
            
            await message.answer(
                f"Assalomu alaykum, <b>{esc(admin_name)}</b>!\n\n"
                f"🏪 Do'kon: <b>{esc(shop_name)}</b>\n"
                f"🆔 Do'kon kodi: <code>{shop_id}</code>\n\n"
                f"Qarzlarni boshqarish, yangi mijoz kiritish va hisobotlarni ko'rish uchun "
                f"pastdagi <b>Do'kon Paneli</b> tugmasini bosing:\n\n"
                f"<i>✏️ Do'kon nomini o'zgartirish uchun: /nomini_ozgartirish</i>",
                parse_mode="HTML",
                reply_markup=get_admin_main_inline_kb(shop_id)
            )
            await message.answer(
                "👇 Mini App menyusi faol:",
                reply_markup=get_admin_reply_kb(shop_id)
            )
            return

        # Faqat bazada umuman do'kon bo'lmagandagina bir marta ro'yxatdan o'tishni boshlaymiz
        await message.answer(
            f"Assalomu alaykum, <b>{esc(message.from_user.full_name)}</b>! 👋\n\n"
            "Siz <b>Do'kon Administratiori</b> (do'kon egasi) sifatida tasdiqlandingiz.\n"
            "Barcha boshqaruv huquqlari sizga beriladi.\n\n"
            "🏪 Iltimos, <b>do'koningiz nomini yozing</b> (masalan: <i>Shox market</i> yoki <i>Baraka Savdo</i>):",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(AdminSetup.waiting_for_shop_name)
        return

    # 2. MIJOZ TEKSHIRUVI (Agar avval raqamini tasdiqlagan bo'lsa)
    customers = await get_customer_by_telegram_id(user_id)
    if customers:
        for cust in customers:
            debts = await get_customer_active_debts(cust["id"])
            total_debt = sum(d["amount"] for d in debts if d.get("status") in ("active", "overdue"))
            
            if total_debt > 0 and debts:
                nearest_due = debts[0]["due_date"]
                products = ", ".join(d["description"] for d in debts[:3])
                if len(debts) > 3:
                    products += f" va yana {len(debts) - 3} ta"
                    
                await message.answer(
                    f"Assalomu alaykum, <b>{esc(cust['full_name'])}</b>! 👋\n\n"
                    f"Sizning <b>{esc(cust.get('shop_name', 'Do\'kon'))}</b> do'konidan qarzingiz bor:\n\n"
                    f"💰 <b>Qarzingiz:</b> <b>{format_amount(total_debt)}</b>\n"
                    f"⏰ <b>To'lash sanasi:</b> <b>{format_date_uz(nearest_due)}</b>\n"
                    f"📦 <b>Nima olingan:</b> {esc(products)}\n\n"
                    f"Qarzlaringizni batafsil ko'rish uchun pastdagi tugmani bosing:",
                    parse_mode="HTML",
                    reply_markup=get_customer_webapp_kb(cust["id"])
                )
            else:
                await message.answer(
                    f"Assalomu alaykum, <b>{esc(cust['full_name'])}</b>! 👋\n\n"
                    f"<b>{esc(cust.get('shop_name', 'Do\'kon'))}</b> do'konida sizning hech qanday qarzingiz yo'q. "
                    f"Barcha to'lovlar to'liq amalga oshirilgan! ✅\n\n"
                    f"Hisob-kitoblar tarixini ko'rish uchun pastdagi tugmani bosing:",
                    parse_mode="HTML",
                    reply_markup=get_customer_webapp_kb(cust["id"])
                )
            
            await message.answer(
                "👇 Shaxsiy hisob menyusi:",
                reply_markup=get_customer_main_kb(cust["id"])
            )
        return

    # 3. YANGI MIJOZ — TELEFON RAQAMINI SO'RAYMIZ
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Ushbu bot orqali do'kondan olgan qarzingiz va to'lov muddatini bilishingiz mumkin.\n\n"
        "Qarzingizni ko'rish uchun pastdagi tugma orqali telefon raqamingizni tasdiqlang:",
        parse_mode="HTML",
        reply_markup=get_phone_request_kb()
    )
    await state.set_state(CustomerVerification.waiting_for_phone)

# ============================================================
# ADMIN ROYXATDAN O'TISH (SETUP)
# ============================================================
@router.message(AdminSetup.waiting_for_shop_name)
async def process_shop_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Do'kon nomi kamida 2 ta harfdan iborat bo'lsin. Iltimos, qaytadan yozing:")
        return
        
    await state.update_data(shop_name=name)
    await message.answer(
        f"Ajoyib! Do'kon nomi: <b>{esc(name)}</b>.\n\n"
        "Endi do'kon egasi sifatida o'zingizning <b>ism va familiyangizni</b> kiriting (masalan: <i>Azizbek Karimov</i>):",
        parse_mode="HTML"
    )
    await state.set_state(AdminSetup.waiting_for_full_name)

@router.message(AdminSetup.waiting_for_full_name)
async def process_admin_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Iltimos, ism va familiyangizni to'liq kiriting:")
        return
        
    await state.update_data(full_name=name)
    await message.answer(
        f"Rahmat, <b>{esc(name)}</b>!\n\n"
        "Oxirgi qadam — mijozlar siz bilan bog'lanishi uchun <b>telefon raqamingizni</b> yuboring:",
        parse_mode="HTML",
        reply_markup=get_phone_request_kb()
    )
    await state.set_state(AdminSetup.waiting_for_phone)

@router.message(AdminSetup.waiting_for_phone)
async def process_admin_phone(message: Message, state: FSMContext):
    phone = ""
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith('+'):
            phone = '+' + phone
    elif message.text:
        is_valid, res = validate_phone(message.text)
        if not is_valid:
            await message.answer("Noto'g'ri format. Iltimos, pastdagi tugmani bosing yoki +998901234567 ko'rinishida yozing:")
            return
        phone = res
    else:
        await message.answer("Iltimos, telefon raqamingizni yuboring.")
        return

    data = await state.get_data()
    shop_name = data.get("shop_name", "Do'kon")
    full_name = data.get("full_name", message.from_user.full_name)
    user_id = message.from_user.id
    
    # Bazada adminni saqlaymiz
    admin = await update_admin_profile(user_id, full_name, shop_name, phone)
    await state.clear()
    
    await message.answer(
        f"🎉 <b>Do'koningiz muvaffaqiyatli ro'yxatdan o'tdi!</b>\n\n"
        f"🏪 Do'kon: <b>{esc(admin['shop_name'])}</b>\n"
        f"👤 Do'kon egasi: <b>{esc(admin['full_name'])}</b>\n"
        f"📞 Telefon: <code>{esc(admin['phone'])}</code>\n"
        f"🆔 Do'kon kodi: <code>{admin['shop_id']}</code>\n\n"
        f"Qarzlarni boshqarish, yangi mijoz kiritish va statistika bilan ishlash uchun pastdagi <b>Do'kon Paneli</b> tugmasini bosing:",
        parse_mode="HTML",
        reply_markup=get_admin_main_inline_kb(admin["shop_id"])
    )
    await message.answer(
        "👇 Mini App menyusi faol:",
        reply_markup=get_admin_reply_kb(admin["shop_id"])
    )

# ============================================================
# DO'KON NOMINI O'ZGARTIRISH BUYRUG'I
# ============================================================
@router.message(Command("nomini_ozgartirish"))
@router.message(Command("edit_shop"))
async def cmd_edit_shop(message: Message, state: FSMContext):
    user_id = message.from_user.id
    admin = await get_admin_by_telegram_id(user_id)
    if not admin and settings.is_admin_id(user_id):
        admin = await get_first_active_admin()
    if not admin:
        await message.answer("Sizda do'kon boshqaruviga ruxsat yo'q.")
        return
        
    await message.answer(
        f"Joriy do'kon nomi: <b>{esc(admin['shop_name'])}</b>\n\n"
        "Yangi do'kon nomini yozing:",
        parse_mode="HTML"
    )
    await state.set_state(AdminEditShop.waiting_for_new_name)

@router.message(AdminEditShop.waiting_for_new_name)
async def process_new_shop_name(message: Message, state: FSMContext):
    new_name = (message.text or "").strip()
    if len(new_name) < 2:
        await message.answer("Do'kon nomi kamida 2 ta harfdan iborat bo'lsin:")
        return
        
    user_id = message.from_user.id
    admin = await get_admin_by_telegram_id(user_id) or await get_first_active_admin()
    if admin:
        await update_admin_shop_name(admin.get("telegram_id", user_id), new_name)
        admin = await get_admin_by_telegram_id(admin.get("telegram_id", user_id)) or admin
        admin["shop_name"] = new_name
    await state.clear()
    
    await message.answer(
        f"✅ <b>Do'kon nomi yangilandi!</b>\n\n"
        f"🏪 Yangi nom: <b>{esc(new_name)}</b>\n\n"
        f"Do'kon boshqaruviga kirish uchun pastdagi tugmani bosing:",
        parse_mode="HTML",
        reply_markup=get_admin_main_inline_kb(admin["shop_id"] if admin else "")
    )

# ============================================================
# ADMIN HUQUQLARINI BOSHQA TELEGRAM ID GA O'TKAZISH
# ============================================================
@router.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    user_id = message.from_user.id
    admin = await get_admin_by_telegram_id(user_id)
    
    is_env_admin = settings.is_admin_id(user_id)
        
    if not is_env_admin and not admin:
        await message.answer("Sizda bunday amalni bajarish huquqi yo'q.")
        return
        
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: <code>/setadmin TELEGRAM_ID</code>\nMasalan: <code>/setadmin 123456789</code>", parse_mode="HTML")
        return
        
    new_admin_id = int(parts[1])
    async with aiosqlite.connect("dokon_hisobi.db") as db:
        if admin:
            await db.execute("UPDATE admins SET telegram_id = ? WHERE id = ?", (new_admin_id, admin["id"]))
        else:
            await db.execute("UPDATE admins SET telegram_id = ? WHERE is_active = 1", (new_admin_id,))
        await db.commit()
        
    await message.answer(
        f"✅ <b>Barcha admin huquqlari yangi Telegram ID ga o'tkazildi:</b> <code>{new_admin_id}</code>\n\n"
        f"Yangi admin botga /start bosib, tizimdan to'liq foydalana oladi.",
        parse_mode="HTML"
    )

# ============================================================
# MIJOZ TELEFON RAQAMINI TEKSHIRISH
# ============================================================
@router.message(CustomerVerification.waiting_for_phone)
async def process_customer_phone(message: Message, state: FSMContext):
    phone = ""
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith('+'):
            phone = '+' + phone
    elif message.text:
        is_valid, res = validate_phone(message.text)
        if not is_valid:
            await message.answer(res)
            return
        phone = res
    else:
        await message.answer("Iltimos, telefon raqamingizni yuboring.")
        return
        
    customers = await get_all_customers_by_phone(phone)
    if not customers:
        await message.answer(
            "❌ <b>Telefon raqamingiz topilmadi</b>\n\n"
            f"<code>{esc(phone)}</code> raqami do'kon tizimida qarzdor sifatida qayd etilmagan.\n"
            "Agar do'kondan qarz olgan bo'lsangiz, do'kon egasiga raqamingizni kiritishini so'rang.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        return
        
    # Telegram ID ni mijoz yozuviga bog'lash
    await link_customer_telegram(phone, message.from_user.id)
    await state.clear()
    
    await message.answer(
        "✅ <b>Raqamingiz tasdiqlandi!</b>",
        reply_markup=ReplyKeyboardRemove()
    )
    
    for cust in customers:
        debts = await get_customer_active_debts(cust["id"])
        total_debt = sum(d["amount"] for d in debts if d.get("status") in ("active", "overdue"))
        
        if total_debt > 0 and debts:
            nearest_due = debts[0]["due_date"]
            products = ", ".join(d["description"] for d in debts[:3])
            if len(debts) > 3:
                products += f" va yana {len(debts) - 3} ta"
                
            await message.answer(
                f"Assalomu alaykum, <b>{esc(cust['full_name'])}</b>! 👋\n\n"
                f"Sizning <b>{esc(cust.get('shop_name', 'Do\'kon'))}</b> do'konidan qarzingiz bor:\n\n"
                f"💰 <b>Qarzingiz:</b> <b>{format_amount(total_debt)}</b>\n"
                f"⏰ <b>To'lash sanasi:</b> <b>{format_date_uz(nearest_due)}</b>\n"
                f"📦 <b>Nima olingan:</b> {esc(products)}\n\n"
                f"Qarzlaringizni batafsil ko'rish uchun pastdagi tugmani bosing:",
                parse_mode="HTML",
                reply_markup=get_customer_webapp_kb(cust["id"])
            )
        else:
            await message.answer(
                f"Assalomu alaykum, <b>{esc(cust['full_name'])}</b>! 👋\n\n"
                f"<b>{esc(cust.get('shop_name', 'Do\'kon'))}</b> do'konida sizning hech qanday qarzingiz yo'q. "
                f"Barcha to'lovlar to'liq amalga oshirilgan! ✅",
                parse_mode="HTML",
                reply_markup=get_customer_webapp_kb(cust["id"])
            )
        await message.answer(
            "👇 Shaxsiy hisob menyusi:",
            reply_markup=get_customer_main_kb(cust["id"])
        )

# Agar admin reply menyudagi "Do'kon Paneli" tugmasini bossa
@router.message(F.text.contains("Do'kon Paneli"))
async def admin_open_panel(message: Message, admin: dict = None):
    user_id = message.from_user.id
    if not admin:
        admin = await get_admin_by_telegram_id(user_id)
        
    if admin and admin.get("shop_name"):
        await message.answer(
            "<b>Do'kon Paneli</b>ni ochish uchun pastdagi tugmani bosing:",
            parse_mode="HTML",
            reply_markup=get_admin_main_inline_kb(admin['shop_id'])
        )
    else:
        await message.answer("Sizda do'kon boshqaruviga ruxsat yo'q.")

# Admin uchun /eslatma komandasi - 19:00 xabarlarini qo'lda tekshirish yoki yuborish
@router.message(Command("eslatma"))
async def cmd_trigger_reminders(message: Message):
    user_id = message.from_user.id
    admin = await get_admin_by_telegram_id(user_id)
    is_env_admin = settings.is_admin_id(user_id)
    
    if not is_env_admin and not admin:
        await message.answer("Sizda bunday amalni bajarish huquqi yo'q.")
        return
        
    from utils.scheduler import send_reminders
    wait_msg = await message.answer("⏳ <b>Qarzdor mijozlarga 19:00 eslatmalari yuborilmoqda...</b>", parse_mode="HTML")
    res = await send_reminders(message.bot)
    
    await wait_msg.edit_text(
        f"✅ <b>Eslatmalar yuborildi!</b>\n\n"
        f"👥 Qarzi bor mijozlar soni: <b>{res.get('total', 0)} ta</b>\n"
        f"📨 Yuborilgan xabarlar: <b>{res.get('sent', 0)} ta</b>\n"
        f"⚠️ Yuborilmadi: <b>{res.get('failed', 0)} ta</b>\n\n"
        f"ℹ️ <i>Eslatmalar har kuni soat 19:00 da avtomatik ravishda barcha qarzdorlarga bot orqali yuboriladi.</i>",
        parse_mode="HTML"
    )
