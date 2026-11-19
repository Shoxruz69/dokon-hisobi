from typing import Optional
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)
from config import settings

def get_phone_request_kb() -> ReplyKeyboardMarkup:
    """Mijoz uchun telefon raqamni yuborish tugmasi"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamimni yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_customer_main_kb(customer_id: Optional[int] = None) -> ReplyKeyboardMarkup:
    """Mijoz uchun menyu — faqat o'z qarzlari va do'kon bilan aloqa"""
    buttons = []
    base_url = settings.MINI_APP_URL or "https://dokon-hisobi.onrender.com"
    if customer_id and base_url.lower().startswith("https://"):
        url = f"{base_url}?role=customer&customer_id={customer_id}&v=2.5"
        buttons.append([KeyboardButton(text="💳 Mening qarzlarim", web_app=WebAppInfo(url=url))])
    else:
        buttons.append([KeyboardButton(text="💳 Mening qarzlarim")])
    buttons.append([KeyboardButton(text="📞 Do'kon bilan bog'lanish")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

def get_customer_inline_kb(customer_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Mijoz inline yangilash va shaxsiy hisob tugmasi"""
    rows = []
    base_url = settings.MINI_APP_URL or "https://dokon-hisobi.onrender.com"
    if customer_id and base_url.lower().startswith("https://"):
        url = f"{base_url}?role=customer&customer_id={customer_id}&v=2.5"
        rows.append([InlineKeyboardButton(text="📱 Shaxsiy hisob (Mini App)", web_app=WebAppInfo(url=url))])
    rows.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="my_debts_refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
