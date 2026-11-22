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
        BotCommand(command="start", description="Tizimni ishga tushirish / Mini App"),
        BotCommand(command="help", description="Yordam va qo'llanma"),
        BotCommand(command="eslatma", description="19:00 eslatmalarini yuborish (Admin)")
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        mini_app_url = settings.MINI_APP_URL or "https://dokon-hisobi.onrender.com"
        if mini_app_url.lower().startswith("https://"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📱 Mini App",
                    web_app=WebAppInfo(url=f"{mini_app_url}?v=2.9")
                )
            )
        logger.info("✅ Bot komandalari va Menu tugmasi muvaffaqiyatli o'rnatildi")
    except Exception as e:
        logger.warning(f"⚠️ Bot komandalarini o'rnatishda xatolik: {e}")

async def main():
    logger.info("🚀 'Dokon Hisobi' tizimi ishga tushirilmoqda...")

    # 1. Mini App va REST API veb-serverini ENG BIRINCHI navbatda ishga tushirish (Render 502 bermasligi uchun)
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.WEB_SERVER_HOST, port=settings.WEB_SERVER_PORT)
    await site.start()
    logger.info(f"🌐 Mini App va REST API veb-serveri muvaffaqiyatli ishga tushdi: http://0.0.0.0:{settings.WEB_SERVER_PORT}")

    # 2. Ma'lumotlar bazasini initsializatsiya qilish
    try:
        await init_db()
        logger.info("✅ Ma'lumotlar bazasi tayyor")
    except Exception as e:
        logger.error(f"⚠️ Baza ulanishida xatolik: {e}")

    # 3. Aiogram Bot va Dispatcher yaratish
    bot = None
    scheduler = None
    try:
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp = Dispatcher()

        # 4. Middleware ulash
        auth_middleware = AuthMiddleware()
        dp.message.middleware(auth_middleware)
        dp.callback_query.middleware(auth_middleware)

        # 5. Routerlarni ro'yxatdan o'tkazish
        dp.include_routers(
            start_router,
            common_router,
            admin_customers_router,
            admin_debts_router,
            admin_stats_router,
            customer_debts_router
        )

        # 6. Komandalar va menyu tugmasini Telegramga o'rnatish
        await setup_bot_commands(bot)

        # 7. Eslatmalar schedulerini ishga tushirish
        scheduler = setup_scheduler(bot)
        scheduler.start()
        logger.info("⏰ Kunlik eslatmalar scheduleri faollashtirildi (19:00)")

        # 8. Webhook tozalash va Pollingni boshlash
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("🤖 Bot xabarlarni qabul qilishga tayyor!")

        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Telegram Bot xatoligi: {e}", exc_info=True)
        # Server 502 bermasligi uchun veb-server ishlab turishini ta'minlaymiz
        while True:
            await asyncio.sleep(3600)
    finally:
        logger.info("🛑 Tizim to'xtatilmoqda...")
        if scheduler:
            scheduler.shutdown()
        await runner.cleanup()
        if bot:
            await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
