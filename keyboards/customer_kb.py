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
    if customer_id and settings.MINI_APP_URL.lower().startswith("https://"):
        url = f"{settings.MINI_APP_URL}?role=customer&customer_id={customer_id}&v=2.3"
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
    if customer_id and settings.MINI_APP_URL.lower().startswith("https://"):
        url = f"{settings.MINI_APP_URL}?role=customer&customer_id={customer_id}&v=2.3"
        rows.append([InlineKeyboardButton(text="📱 Shaxsiy hisob (Mini App)", web_app=WebAppInfo(url=url))])
    rows.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="my_debts_refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
