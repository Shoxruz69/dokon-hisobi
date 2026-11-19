import os
from pydantic_settings import BaseSettings
from typing import Optional, List, Union

class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    ADMIN_TELEGRAM_ID: Union[int, str] = ""
    MINI_APP_URL: str = ""
    DATABASE_URL: str = ""
    ADMIN_SECRET_CODE: str = "DOKON2024"
    TIMEZONE: str = "Asia/Tashkent"
    WEB_SERVER_HOST: str = "0.0.0.0"
    WEB_SERVER_PORT: int = int(os.getenv("PORT", os.getenv("WEB_SERVER_PORT", 8080)))

    def get_admin_ids(self) -> List[int]:
        ids = []
        for part in str(self.ADMIN_TELEGRAM_ID).replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    def is_admin_id(self, user_id: Union[int, str]) -> bool:
        try:
            uid = int(user_id)
            return uid in self.get_admin_ids()
        except Exception:
            return False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
