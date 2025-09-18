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
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "").strip()
    PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "").strip()
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "381764678").strip()
    YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "TEST:142244").strip()
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip()
    LOG_FILE: str = os.getenv("LOG_FILE", "").strip()

    @classmethod
    def validate(cls) -> bool:
        # Отладочная информация
        print(f"DEBUG: TELEGRAM_TOKEN = '{cls.TELEGRAM_TOKEN}'")
        print(f"DEBUG: PERPLEXITY_API_KEY = '{cls.PERPLEXITY_API_KEY[:10]}...'")
        
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN не установлен")
        if not cls.PERPLEXITY_API_KEY:
            raise ValueError("PERPLEXITY_API_KEY не установлен")
        return True
