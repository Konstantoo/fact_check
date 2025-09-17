import aiohttp
import asyncio
from loguru import logger
from app_config import Config

class DeepResearchService:
    def __init__(self) -> None:
        self.api_key = Config.PERPLEXITY_API_KEY
        self.base_url = "https://api.perplexity.ai/chat/completions"
        
    async def conduct_deep_research(self, topic: str, initial_analysis: str) -> str:
        """Проводит углубленное исследование с использованием дорогой модели"""
        
        # Формируем промпт на основе простого анализа
        research_prompt = self._generate_research_prompt(topic, initial_analysis)
        
        messages = [
            {
                "role": "system",
                "content": """Ты ведущий эксперт-исследователь с доступом к самым авторитетным источникам. 
                Твоя задача - провести максимально глубокое и всестороннее исследование темы.

                ОБЯЗАТЕЛЬНО включи:
                1. 📊 **ДЕТАЛЬНЫЙ АНАЛИЗ** - глубокий разбор всех аспектов темы
                2. 🔍 **ЭКСПЕРТНЫЕ МНЕНИЯ** - цитаты от ведущих специалистов
                3. 📚 **АВТОРИТЕТНЫЕ ИСТОЧНИКИ** - ссылки на научные работы, официальные документы
                4. 📈 **СТАТИСТИКА И ДАННЫЕ** - конкретные цифры и факты
                5. ⚖️ **МНОГОСТОРОННИЙ ВЗГЛЯД** - различные точки зрения на проблему
                6. 🎯 **ПРАКТИЧЕСКИЕ ВЫВОДЫ** - рекомендации и прогнозы
                
                Используй только проверенные, авторитетные источники.
                Каждый факт должен быть подкреплен ссылкой."""
            },
            {
                "role": "user",
                "content": research_prompt
            }
        ]
        
        payload = {
            "model": "sonar-deep-research",  # Дорогая модель для Deep Research
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.3,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Запускаем Deep Research для темы: {topic[:100]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    logger.info(f"Deep Research завершен, получено {len(content)} символов")
                    return content
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка Deep Research API: {response.status} - {error_text}")
                    return f"❌ Ошибка при проведении Deep Research: {response.status}"
    
    def _generate_research_prompt(self, topic: str, initial_analysis: str) -> str:
        """Генерирует детальный промпт для Deep Research на основе простого анализа"""
        
        prompt = f"""Проведи максимально глубокое исследование по теме: {topic}

НА ОСНОВЕ ПРЕДВАРИТЕЛЬНОГО АНАЛИЗА:
{initial_analysis}

ЗАДАЧИ ДЛЯ DEEP RESEARCH:
1. Найди дополнительные независимые источники, которые НЕ упоминались в предварительном анализе
2. Проведи поиск экспертных мнений и интервью по данной теме
3. Найди статистические данные и исследования
4. Проанализируй исторический контекст и аналогичные случаи
5. Найди официальные документы и нормативные акты
6. Проведи сравнительный анализ с международным опытом
7. Найди противоположные точки зрения и критику
8. Предложи прогнозы развития ситуации

ТРЕБОВАНИЯ К ИСТОЧНИКАМ:
- Научные публикации и исследования
- Официальные документы и отчеты
- Интервью с экспертами
- Статистические данные
- Международные источники
- Исторические материалы

ФОРМАТ ОТВЕТА:
- Структурированный анализ по разделам
- Конкретные цитаты с указанием источников
- Статистические данные с датами
- Ссылки на все источники в формате [Название](URL)
- Практические выводы и рекомендации

ВАЖНО: Это углубленное исследование, поэтому ищи максимально детальную и авторитетную информацию."""
        
        return prompt
