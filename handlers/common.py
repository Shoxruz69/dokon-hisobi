from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

router = Router()

@router.message(Command("cancel"))
@router.message(F.text == "❌ Bekor qilish")
async def cmd_cancel(message: Message, state: FSMContext):
    """Joriy amalni bekor qilish"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Hech qanday faol amal yo'q.")
        return
        
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Yordam va qo'llanma"""
    text = (
        "🤖 <b>Dokon Hisobi botidan foydalanish qo'llanmasi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔹 <b>Do'kon egalari uchun:</b>\n"
        "• /start — Bosh menyu va do'kon ma'lumotlari\n"
        "• 🏪 <b>Do'kon Paneli</b> — Chiroyli Mini App interfeysi\n"
        "• ➕ <b>Yangi qarz</b> — Mijoz va qarz qo'shish\n"
        "• 👥 <b>Mijozlar</b> — Barcha qarzdorlar ro'yxati va qidiruv\n"
        "• 📊 <b>Statistika</b> — Qarzlar umumiy summasi va hisobotlar\n\n"
        "🔹 <b>Mijozlar uchun:</b>\n"
        "• 💳 <b>Mening qarzlarim</b> — Olingan narsalar va to'lov muddati\n"
        "• 📞 <b>Do'kon bilan bog'lanish</b> — Do'kondor bilan aloqa\n\n"
        "⏰ <i>Eslatma: Har kuni ertalab soat 09:00 da bot yaqinlashib kelayotgan qarzlar haqida eslatma yuboradi.</i>"
    )
    await message.answer(text, parse_mode="HTML")

