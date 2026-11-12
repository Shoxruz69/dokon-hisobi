import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonWebApp, WebAppInfo

from config import settings
from database.db import init_db
from middlewares.auth import AuthMiddleware
from handlers import (
    start_router,
    common_router,
    admin_customers_router,
    admin_debts_router,
    admin_stats_router,
    customer_debts_router
)
from utils.scheduler import setup_scheduler
from api.routes import create_web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DokonHisobi")

async def setup_bot_commands(bot: Bot):
    """Telegram menyusidagi komandalar va Menu tugmasini sozlash"""
    commands = [
        BotCommand(command="start", description="Tizimni ishga tushirish"),
        BotCommand(command="help", description="Yordam va ma'lumot"),
        BotCommand(command="eslatma", description="Qarzdorlarga eslatma yuborish (Admin)")
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        if settings.MINI_APP_URL.lower().startswith("https://"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Do'kon Paneli",
                    web_app=WebAppInfo(url=f"{settings.MINI_APP_URL}?v=2.1")
                )
            )
        logger.info("✅ Bot komandalari va Menu tugmasi muvaffaqiyatli o'rnatildi")
    except Exception as e:
        logger.warning(f"⚠️ Bot komandalarini o'rnatishda xatolik: {e}")

async def main():
    logger.info("🚀 'Dokon Hisobi' tizimi ishga tushirilmoqda...")

    # 1. Ma'lumotlar bazasini initsializatsiya qilish
    await init_db()

    # 2. Aiogram Bot va Dispatcher yaratish
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # 3. Middleware ulash
    auth_middleware = AuthMiddleware()
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)

    # 4. Routerlarni ro'yxatdan o'tkazish
    dp.include_routers(
        start_router,
        common_router,
        admin_customers_router,
        admin_debts_router,
        admin_stats_router,
        customer_debts_router
    )

    # 5. Komandalarni Telegramga yozish
    await setup_bot_commands(bot)

    # 6. Eslatmalar schedulerini ishga tushirish
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("⏰ Kunlik eslatmalar scheduleri faollashtirildi (19:00)")

    # 7. Mini App va REST API uchun aiohttp veb serverini ishga tushirish
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.WEB_SERVER_HOST, port=settings.WEB_SERVER_PORT)
    await site.start()
    logger.info(f"🌐 Mini App va REST API serveri ishga tushdi: http://localhost:{settings.WEB_SERVER_PORT}")

    # 8. Bot pollingni boshlash
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("🤖 Bot xabarlarni qabul qilishga tayyor!")

    try:
        await dp.start_polling(bot)
    finally:
        logger.info("🛑 Tizim to'xtatilmoqda...")
        scheduler.shutdown()
        await runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")

