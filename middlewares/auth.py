from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.queries import get_admin_by_telegram_id, get_customer_by_telegram_id

class AuthMiddleware(BaseMiddleware):
    """Foydalanuvchi turini (Admin / Mijoz) aniqlovchi middleware"""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user:
            # Admin ekanligini tekshirish
            admin = await get_admin_by_telegram_id(user.id)
            data["admin"] = admin
            
            # Agar admin bo'lmasa, mijoz yozuvlarini tekshirish
            if not admin:
                customers = await get_customer_by_telegram_id(user.id)
                data["customers"] = customers
            else:
                data["customers"] = []
                
        return await handler(event, data)

