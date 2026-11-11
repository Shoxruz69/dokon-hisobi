from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)
from config import settings

def get_admin_main_inline_kb(shop_id: str) -> InlineKeyboardMarkup:
    """Admin uchun barcha boshqaruvni ochuvchi Mini App tugmasi"""
    mini_app_url = f"{settings.MINI_APP_URL}?shop_id={shop_id}&v=2.1"
    
    if mini_app_url.lower().startswith("https://"):
        panel_btn = InlineKeyboardButton(
            text="Do'kon Paneli (Mini App)",
            web_app=WebAppInfo(url=mini_app_url)
        )
    else:
        panel_btn = InlineKeyboardButton(
            text="Do'kon Paneli (Mini App)",
            url=mini_app_url
        )
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [panel_btn]
    ])

def get_admin_reply_kb(shop_id: str) -> ReplyKeyboardMarkup:
    """Admin doimiy pastki menyusi — faqat Mini App tugmasi"""
    mini_app_url = f"{settings.MINI_APP_URL}?shop_id={shop_id}&v=2.1"
    
    if mini_app_url.lower().startswith("https://"):
        panel_btn = KeyboardButton(text="Do'kon Paneli", web_app=WebAppInfo(url=mini_app_url))
    else:
        panel_btn = KeyboardButton(text="Do'kon Paneli")
        
    return ReplyKeyboardMarkup(
        keyboard=[
            [panel_btn]
        ],
        resize_keyboard=True
    )

def get_customer_actions_kb(customer_id: int) -> InlineKeyboardMarkup:
    """Mijoz kartochkasi amallari"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Qarz qo'shish", callback_data=f"add_debt_to_{customer_id}"),
            InlineKeyboardButton(text="Qarzlar tarixi", callback_data=f"cust_debts_{customer_id}")
        ],
        [
            InlineKeyboardButton(text="Ortga", callback_data="back_to_customers")
        ]
    ])

def get_debt_actions_kb(debt_id: int, customer_id: int, is_paid: bool = False) -> InlineKeyboardMarkup:
    """Alohida qarz amallari"""
    buttons = []
    if not is_paid:
        buttons.append([InlineKeyboardButton(text="To'landi deb belgilash", callback_data=f"pay_debt_{debt_id}")])
    buttons.append([InlineKeyboardButton(text="Ortga", callback_data=f"cust_debts_{customer_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
