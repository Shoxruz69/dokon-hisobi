from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command

from database.queries import get_admin_by_telegram_id, get_admin_stats
from utils.formatters import build_admin_stats_text
from config import settings

router = Router()

@router.message(Command("stats"))
@router.message(F.text == "📊 Statistika")
@router.callback_query(F.data == "stats")
async def show_store_stats(event: Message | CallbackQuery, admin: dict = None):
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
        
    stats = await get_admin_stats(admin["shop_id"])
    text = build_admin_stats_text(stats, admin["shop_name"])
    
    mini_app_url = f"{settings.MINI_APP_URL}?shop_id={admin['shop_id']}"
    if mini_app_url.lower().startswith("https://"):
        panel_btn = InlineKeyboardButton(text="🏪 Do'kon Paneli (Mini App)", web_app=WebAppInfo(url=mini_app_url))
    else:
        panel_btn = InlineKeyboardButton(text="🏪 Do'kon Paneli (Havola)", url=mini_app_url)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [panel_btn],
        [
            InlineKeyboardButton(text="👥 Mijozlar ro'yxati", callback_data="customers_list"),
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="stats")
        ]
    ])
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)

