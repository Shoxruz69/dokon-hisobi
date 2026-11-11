from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

def get_phone_request_kb() -> ReplyKeyboardMarkup:
    """Mijoz uchun telefon raqamni yuborish tugmasi"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamimni yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_customer_main_kb() -> ReplyKeyboardMarkup:
    """Mijoz uchun menyu — faqat o'z qarzlari va do'kon bilan aloqa"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Mening qarzlarim")],
            [KeyboardButton(text="📞 Do'kon bilan bog'lanish")]
        ],
        resize_keyboard=True
    )

def get_customer_inline_kb() -> InlineKeyboardMarkup:
    """Mijoz inline yangilash tugmasi"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="my_debts_refresh")]
    ])
