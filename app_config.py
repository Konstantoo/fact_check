import os
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

class Config:
    """Конфигурация приложения"""
    
    # Статические переменные
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "")
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "381764678")
    YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "TEST:142244")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "")

    @classmethod
    def validate(cls) -> bool:
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN не установлен")
        if not cls.PERPLEXITY_API_KEY:
            raise ValueError("PERPLEXITY_API_KEY не установлен")
        return True
