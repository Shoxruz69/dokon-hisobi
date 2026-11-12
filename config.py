import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    BOT_TOKEN: str = "9123131223:AAFKwc8X9xQhbvpVYUr7r6jhGrD-WEhSNoI"
    ADMIN_TELEGRAM_ID: int = 6876312568
    MINI_APP_URL: str = "https://dokon-hisobi.onrender.com"
    DATABASE_URL: str = "postgresql://postgres.paurqmioymjjqsollezd:Shoxruz2010!@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres"
    ADMIN_SECRET_CODE: str = "DOKON2024"
    TIMEZONE: str = "Asia/Tashkent"
    WEB_SERVER_HOST: str = "0.0.0.0"
    WEB_SERVER_PORT: int = int(os.getenv("PORT", os.getenv("WEB_SERVER_PORT", 8080)))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
