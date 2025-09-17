import aiohttp
from typing import Optional


class FactCheckerService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def check_fact(self, statement: str) -> str:
        # Минимальная заглушка для запуска
        return f"TL;DR: Проверка утверждения выполнена. Утверждение: {statement[:200]}...\n\nИсточники: будут добавлены (Perplexity)."
