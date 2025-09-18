import aiohttp
from typing import Optional
from loguru import logger

class FactCheckerService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai/chat/completions"

    async def check_fact(self, statement: str) -> str:
        """Проверяет факт с помощью Perplexity API"""
        logger.info(f"Проверяем факт: {statement}")
        
        messages = [
            {
                "role": "system",
                "content": """Ты независимый факт-чекер. Твоя задача - проверить утверждение и дать объективную оценку.

ОБЯЗАТЕЛЬНО включи в ответ:
1. 📋 КРАТКИЙ ВЫВОД - истинность утверждения (истинно/ложно/частично истинно)
2. 🔍 ПРОВЕРКА ФАКТОВ - что подтверждено, что опровергнуто
3. 📚 ИСТОЧНИКИ ВЕРИФИКАЦИИ - 3-5 проверенных источников с ссылками
4. ⚠️ КОНТЕКСТ - важные оговорки и нюансы
5. 🎯 РЕКОМЕНДАЦИИ - как читателю лучше оценить информацию

ВАЖНО:
- Отвечай ТОЛЬКО на русском языке
- Используй только проверенные, независимые источники
- Формат ссылок: [Название источника](URL)
- Будь объективным и беспристрастным"""
            },
            {
                "role": "user",
                "content": f"Проверь это утверждение: {statement}"
            }
        ]
        
        payload = {
            "model": "sonar",
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.3,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data['choices'][0]['message']['content']
                        logger.info(f"Факт-чек завершен, получено {len(result)} символов")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка API факт-чека: {response.status} - {error_text}")
                        return f"❌ Ошибка при проверке факта: {response.status}"
        except Exception as e:
            logger.error(f"Ошибка при проверке факта: {str(e)}")
            return f"❌ Ошибка при проверке факта: {str(e)}"
