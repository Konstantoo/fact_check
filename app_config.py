import os
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

class Config:
    """Конфигурация приложения"""
    
    # Вспомогательная очистка значений переменных окружения
    @staticmethod
    def _clean(value: Optional[str]) -> str:
        if value is None:
            return ""
        cleaned = value.strip().strip('"').strip("'")
        if cleaned.startswith('='):
            cleaned = cleaned[1:]
        return cleaned.strip()
    
    # Статические переменные
    TELEGRAM_TOKEN: str = _clean.__func__(os.getenv("TELEGRAM_TOKEN", ""))
    PERPLEXITY_API_KEY: str = _clean.__func__(os.getenv("PERPLEXITY_API_KEY", ""))
    YOOKASSA_SHOP_ID: str = _clean.__func__(os.getenv("YOOKASSA_SHOP_ID", "381764678"))
    YOOKASSA_SECRET_KEY: str = _clean.__func__(os.getenv("YOOKASSA_SECRET_KEY", "TEST:142244"))
    LOG_LEVEL: str = _clean.__func__(os.getenv("LOG_LEVEL", "INFO"))
    LOG_FILE: str = _clean.__func__(os.getenv("LOG_FILE", ""))

    @classmethod
    def validate(cls) -> bool:
        # Отладочная информация (с маскировкой)
        def _mask(val: str, head: int = 6) -> str:
            if not val:
                return ""
            return val[:head] + "..."
        print(f"DEBUG: TELEGRAM_TOKEN = '{_mask(cls.TELEGRAM_TOKEN)}'")
        print(f"DEBUG: PERPLEXITY_API_KEY = '{_mask(cls.PERPLEXITY_API_KEY)}'")
        
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN не установлен")
        if not cls.PERPLEXITY_API_KEY:
            raise ValueError("PERPLEXITY_API_KEY не установлен")
        return True
