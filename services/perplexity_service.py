import aiohttp
import json
from typing import Optional
from loguru import logger


class PerplexityService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai/chat/completions"

    async def _make_request(self, messages: list) -> str:
        """Выполняет запрос к Perplexity API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar",
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.2,
            "stream": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data["choices"][0]["message"]["content"]
                        logger.info(f"Получен ответ от Perplexity API: {result[:300]}...")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Perplexity API error {response.status}: {error_text}")
                        return f"❌ Ошибка API: {response.status}"
        except Exception as e:
            logger.error(f"Ошибка при запросе к Perplexity API: {e}")
            return f"❌ Ошибка подключения к API: {str(e)}"

    async def analyze_article(self, url: str) -> str:
        """Анализирует статью по ссылке"""
        logger.info(f"Анализируем статью: {url}")
        logger.info(f"Полный URL для анализа: '{url}'")
        
        messages = [
            {
                "role": "system",
                "content": """Ты независимый аналитик новостей. Твоя задача - провести объективный анализ статьи, проверить факты и оценить качество источников.

ОБЯЗАТЕЛЬНО включи в анализ:
1. 📋 КРАТКИЙ ВЫВОД - основная суть статьи
2. 🔍 ПРОВЕРКА ФАКТОВ - что подтверждено, что требует проверки
3. 📚 НЕЗАВИСИМЫЕ ИСТОЧНИКИ - найди 3-5 проверенных источников по теме с КОНКРЕТНЫМИ ССЫЛКАМИ
4. ⚠️ ПОТЕНЦИАЛЬНЫЕ ПРОБЛЕМЫ - возможные искажения или предвзятость
5. 🎯 РЕКОМЕНДАЦИИ - как читателю лучше оценить информацию

КРИТИЧЕСКИ ВАЖНО:
- ВСЕГДА предоставляй конкретные ссылки на источники верификации
- Каждый факт должен быть подкреплен ссылкой на независимый источник
- Используй только проверенные, независимые источники
- Формат ссылок: [Название источника](URL)
- Минимум 3-5 ссылок на независимые источники"""
            },
            {
                "role": "user", 
                "content": f"Проанализируй эту конкретную статью: {url}\n\nВАЖНО: Анализируй именно эту ссылку, а не похожие статьи. Проведи полный факт-чекинг и найди независимые источники для проверки информации из этой конкретной статьи.\n\nОБЯЗАТЕЛЬНО предоставь:\n- Конкретные ссылки на источники верификации\n- Минимум 3-5 независимых источников\n- Формат: [Название источника](URL)\n- Каждый факт должен быть подкреплен ссылкой"
            }
        ]
        
        logger.info(f"Отправляем в API сообщение: {messages[1]['content']}")
        return await self._make_request(messages)

    async def analyze_text(self, text: str) -> str:
        """Анализирует текст"""
        logger.info(f"Анализируем текст: {text[:100]}...")
        
        messages = [
            {
                "role": "system",
                "content": """Ты независимый аналитик новостей. Твоя задача - провести объективный анализ текста, проверить факты и оценить качество источников.

ОБЯЗАТЕЛЬНО включи в анализ:
1. 📋 КРАТКИЙ ВЫВОД - основная суть текста
2. 🔍 ПРОВЕРКА ФАКТОВ - что подтверждено, что требует проверки  
3. 📚 НЕЗАВИСИМЫЕ ИСТОЧНИКИ - найди 3-5 проверенных источников по теме
4. ⚠️ ПОТЕНЦИАЛЬНЫЕ ПРОБЛЕМЫ - возможные искажения или предвзятость
5. 🎯 РЕКОМЕНДАЦИИ - как читателю лучше оценить информацию

АНАЛИЗИРУЙ ВСЕ ИСТОЧНИКИ, но с учетом их надежности!
Используй только проверенные, независимые источники."""
            },
            {
                "role": "user",
                "content": f"Проанализируй этот текст: {text}\n\nПроведи полный факт-чекинг и найди независимые источники для проверки информации."
            }
        ]
        
        return await self._make_request(messages)

    async def check_fact(self, fact: str) -> str:
        """Проверяет конкретный факт"""
        logger.info(f"Проверяем факт: {fact[:100]}...")
        
        messages = [
            {
                "role": "system", 
                "content": """Ты независимый факт-чекер. Твоя задача - проверить конкретный факт, найти подтверждения или опровержения.

ОБЯЗАТЕЛЬНО включи:
1. 📋 ВЕРДИКТ - подтверждено/опровергнуто/требует проверки
2. 🔍 ДОКАЗАТЕЛЬСТВА - конкретные факты и источники
3. 📚 НЕЗАВИСИМЫЕ ИСТОЧНИКИ - 3-5 проверенных источников
4. ⚠️ КОНТЕКСТ - важные детали и нюансы
5. 🎯 РЕКОМЕНДАЦИИ - как лучше проверить информацию

АНАЛИЗИРУЙ ВСЕ ИСТОЧНИКИ, но с учетом их надежности!
Используй только проверенные, независимые источники."""
            },
            {
                "role": "user",
                "content": f"Проверь этот факт: {fact}\n\nНайди независимые источники для подтверждения или опровержения."
            }
        ]
        
        return await self._make_request(messages)
