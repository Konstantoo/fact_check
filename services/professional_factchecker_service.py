import aiohttp
import json
import asyncio
from typing import Dict, List, Optional, Tuple
from loguru import logger
from services.source_validator_service import SourceValidatorService
from datetime import datetime
import re

class ProfessionalFactCheckerService:
    """
    Профессиональный сервис фактчекинга версии 2.0
    Основан на лучших практиках IFCN и профессиональных стандартах
    """
    
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai/chat/completions"
        
        # Профессиональные стандарты фактчекинга
        self.factchecking_standards = {
            "verification_levels": [
                "✅ ПОДТВЕРЖДЕНО - информация проверена по множественным независимым источникам",
                "⚠️ ЧАСТИЧНО ПОДТВЕРЖДЕНО - некоторые аспекты подтверждены, другие требуют дополнительной проверки",
                "❌ ОПРОВЕРГНУТО - информация противоречит проверенным фактам",
                "❓ НЕ УДАЛОСЬ ПРОВЕРИТЬ - недостаточно данных для однозначного заключения",
                "🔄 ТРЕБУЕТ ОБНОВЛЕНИЯ - информация устарела или изменилась"
            ],
            "source_priorities": [
                "1. Академические исследования и peer-reviewed публикации",
                "2. Официальные документы и отчеты государственных органов",
                "3. Международные организации (ООН, ВОЗ, МВФ и др.)",
                "4. Репутационные СМИ с проверенными редакционными стандартами",
                "5. Экспертные мнения и интервью с признанными специалистами",
                "6. Статистические данные и официальная отчетность"
            ]
        }

    async def conduct_professional_factcheck(self, statement: str, context: str = "") -> Dict:
        """
        Проводит профессиональную проверку факта с многоуровневым анализом
        """
        logger.info(f"Начинаем профессиональную проверку факта: {statement[:100]}...")
        
        # Этап 1: Первичный анализ и структурирование
        primary_analysis = await self._primary_analysis(statement, context)
        
        # Этап 2: Глубокое исследование источников
        source_investigation = await self._source_investigation(statement, primary_analysis)
        
        # Этап 3: Критический анализ и верификация
        critical_analysis = await self._critical_analysis(statement, source_investigation)
        
        # Доп. этап: Поиск манипуляций и риторических приемов
        manipulation_analysis = await self._detect_manipulation(statement, source_investigation, critical_analysis)

        # Этап 4: Формирование заключения
        final_verdict = await self._form_final_verdict(statement, critical_analysis)
        
        # Проверяем количество академических источников
        academic_sources_count = self._count_academic_sources_in_analysis(source_investigation, critical_analysis)
        
        confidence = self._calculate_confidence_score(critical_analysis)
        level_text = self._determine_verification_level(final_verdict)
        level_text = self._adjust_verification_with_confidence(level_text, confidence, final_verdict)

        return {
            "statement": statement,
            "timestamp": datetime.now().isoformat(),
            "primary_analysis": primary_analysis,
            "source_investigation": source_investigation,
            "critical_analysis": critical_analysis,
            "final_verdict": final_verdict,
            "manipulation_analysis": manipulation_analysis,
            "verification_level": level_text,
            "confidence_score": confidence,
            "academic_sources_count": academic_sources_count,
            "recommendations": self._generate_recommendations(final_verdict)
        }

    async def _primary_analysis(self, statement: str, context: str) -> Dict:
        """Первичный анализ утверждения"""
        messages = [
            {
                "role": "system",
                "content": """Ты профессиональный факт-чекер с многолетним опытом. Твоя задача - провести первичный анализ утверждения.

ОБЯЗАТЕЛЬНО выполни:
1. 📋 СТРУКТУРИРОВАНИЕ - разбей утверждение на проверяемые компоненты
2. 🎯 КЛЮЧЕВЫЕ ЭЛЕМЕНТЫ - выдели факты, цифры, даты, имена, события
3. 🔍 ТИП УТВЕРЖДЕНИЯ - определи категорию (статистика, событие, мнение, прогноз)
4. ⚠️ ПОТЕНЦИАЛЬНЫЕ ПРОБЛЕМЫ - выяви возможные искажения или манипуляции
5. 📊 КОНТЕКСТ - определи важность и актуальность для проверки

ФОРМАТ ОТВЕТА (строго на русском языке):
- Структурированный анализ по пунктам
- Четкое разделение фактов и интерпретаций
- Указание на сложные для проверки элементы
- Предварительная оценка достоверности (1-10)"""
            },
            {
                "role": "user",
                "content": f"Проведи первичный анализ утверждения: {statement}\n\nКонтекст: {context if context else 'Не предоставлен'}"
            }
        ]
        
        result = await self._make_request(messages, max_tokens=2000)
        return {"analysis": result, "timestamp": datetime.now().isoformat()}

    async def _source_investigation(self, statement: str, primary_analysis: Dict) -> Dict:
        """Глубокое исследование источников с приоритетом академических источников"""
        messages = [
            {
                "role": "system",
                "content": """Ты эксперт по поиску и анализу источников. Твоя задача - найти максимально надежные источники для проверки утверждения.

КРИТИЧЕСКИ ВАЖНО:
1. 🔍 АКАДЕМИЧЕСКИЕ ИСТОЧНИКИ - найди МИНИМУМ 5 академических источников (peer-reviewed статьи, научные журналы, whitepaper)
2. 📚 КАТЕГОРИЗАЦИЯ - раздели источники по типам и надежности
3. ⚖️ БАЛАНС МНЕНИЙ - найди различные точки зрения на проблему
4. 🎯 ПРЯМЫЕ ИСТОЧНИКИ - приоритет первоисточникам и официальным данным
5. 📊 СТАТИСТИКА - найди количественные данные и исследования
6. 🌍 МЕЖДУНАРОДНЫЙ КОНТЕКСТ - включи международные источники для сравнения

ОБЯЗАТЕЛЬНЫЕ ПРИОРИТЕТЫ ИСТОЧНИКОВ (в порядке важности):
1. Академические исследования и peer-reviewed публикации (Nature, Science, PubMed, arXiv, JSTOR)
2. Whitepaper и технические отчеты от компаний и организаций
3. Официальные документы и отчеты государственных органов
4. Международные организации (ООН, ВОЗ, МВФ, Всемирный банк)
5. Репутационные СМИ с проверенными редакционными стандартами
6. Экспертные мнения и интервью с признанными специалистами
7. Статистические данные и официальная отчетность

ТРЕБОВАНИЯ К АКАДЕМИЧЕСКИМ ИСТОЧНИКАМ:
- Peer-reviewed научные статьи
- Исследования из рецензируемых журналов
- Академические whitepaper
- Научные отчеты от университетов и исследовательских институтов
- Статистические исследования от официальных организаций

ПОИСК ВЕДИ НА ЛЮБОМ ЯЗЫКЕ (EN/RU/ES/DE/FR/CHN и др.), НО
ФОРМАТ ОТВЕТА (строго на русском языке):
- Список источников с категоризацией (обязательно выдели академические)
- Оценка надежности каждого источника
- Анализ покрытия темы источниками
- Выявление пробелов в источниках
- ПОДСЧЕТ: сколько академических источников найдено (должно быть ≥5)"""
            },
            {
                "role": "user",
                "content": f"Найди надежные источники для проверки утверждения: {statement}\n\nПервичный анализ: {primary_analysis.get('analysis', '')}\n\nВАЖНО: Найди минимум 5 академических источников (peer-reviewed статьи, whitepaper, научные исследования)."
            }
        ]
        
        result = await self._make_request(messages, max_tokens=3000)
        return {"sources": result, "timestamp": datetime.now().isoformat()}

    async def _critical_analysis(self, statement: str, source_investigation: Dict) -> Dict:
        """Критический анализ и верификация с приоритетом академических источников"""
        messages = [
            {
                "role": "system",
                "content": """Ты ведущий эксперт по критическому анализу информации. Твоя задача - провести глубокую верификацию утверждения.

ОБЯЗАТЕЛЬНО выполни:
1. 🔍 ВЕРИФИКАЦИЯ ФАКТОВ - проверь каждый факт по найденным источникам
2. 📊 АНАЛИЗ ДАННЫХ - проанализируй статистику и цифры
3. ⚖️ СРАВНИТЕЛЬНЫЙ АНАЛИЗ - сопоставь информацию из разных источников
4. 🎯 ВЫЯВЛЕНИЕ ПРОТИВОРЕЧИЙ - найди расхождения между источниками
5. 📈 ОЦЕНКА ДОСТОВЕРНОСТИ - определи уровень подтверждения каждого элемента
6. ⚠️ КРИТИЧЕСКИЕ ЗАМЕЧАНИЯ - выяви слабые места в аргументации
7. 🔄 АКТУАЛЬНОСТЬ - проверь актуальность информации

ПРИОРИТЕТ АКАДЕМИЧЕСКИМ ИСТОЧНИКАМ:
- В первую очередь используй peer-reviewed статьи и научные исследования
- Применяй данные из whitepaper и технических отчетов
- Официальные документы и отчеты государственных органов
- Международные организации и репутационные СМИ

МЕТОДОЛОГИЯ:
- Используй принцип множественных источников (минимум 5 академических)
- Применяй скептический подход
- Проверяй контекст и интерпретацию
- Учитывай возможные предвзятости источников
- ПОДСЧИТАЙ: сколько академических источников использовано

ИСПОЛЬЗУЙ ИСТОЧНИКИ НА ЛЮБОМ ЯЗЫКЕ, НО
ФОРМАТ ОТВЕТА (строго на русском языке):
- Детальная верификация по пунктам
- Конкретные доказательства и опровержения
- Анализ надежности источников
- Выводы по каждому аспекту утверждения
- УКАЖИ: количество использованных академических источников"""
            },
            {
                "role": "user",
                "content": f"Проведи критический анализ утверждения: {statement}\n\nНайденные источники: {source_investigation.get('sources', '')}\n\nВАЖНО: Используй минимум 5 академических источников для качественной проверки."
            }
        ]
        
        result = await self._make_request(messages, max_tokens=4000)
        return {"verification": result, "timestamp": datetime.now().isoformat()}

    async def _detect_manipulation(self, statement: str, source_investigation: Dict, critical_analysis: Dict) -> Dict:
        """Определяет признаки манипуляции и риторические приемы (логические ошибки, приемы пропаганды)."""
        messages = [
            {
                "role": "system",
                "content": """Ты эксперт по медиаграмотности и критическому мышлению. Излагай выводы кратко и деловым языком (стиль executive summary).

ОБЯЗАТЕЛЬНО:
1. 🎭 ИДЕНТИФИКАЦИЯ ПРИЕМОВ — назови конкретные техники, если они встречаются:
   • апелляция к эмоциям, страх/паника, сенсационность, демонизация
   • whataboutism
   • подмена тезиса, соломенное чучело, ложная дилемма
   • cherry-picking (выборочные факты), ложная эквиваленция
   • ad hominem, guilt by association, ореол/рогатый эффект
   • манипуляции статистикой, неопределенные источники («эксперты считают»)
   • конспирологические маркеры, обобщения («все», «никто»)
2. 🧪 ПРИМЕРЫ — процитируй 1–2 характерных фрагмента (или перефразируй), к каждому укажи прием
3. 📏 СТЕПЕНЬ ВЛИЯНИЯ — низкая/средняя/высокая
4. 🛡 РЕКОМЕНДАЦИИ — как читать материал критически и что перепроверить

ФОРМАТ (строго на русском):
- Список приемов (название → объяснение → пример → степень влияния)
- Общая оценка манипулятивности
- Рекомендации для читателя"""
            },
            {
                "role": "user",
                "content": f"Определи манипуляции и риторические приемы применительно к утверждению: {statement}\n\nНайденные источники: {source_investigation.get('sources','')}\n\nКритический анализ: {critical_analysis.get('verification','')}"
            }
        ]
        result = await self._make_request(messages, max_tokens=1800)
        return {"manipulation": result, "timestamp": datetime.now().isoformat()}

    async def _form_final_verdict(self, statement: str, critical_analysis: Dict) -> Dict:
        """Формирование финального заключения"""
        messages = [
            {
                "role": "system",
                "content": """Ты главный редактор фактчекингового агентства. Сформулируй финальное заключение в стиле executive summary (McKinsey/BCG): деловой тон, ясность, конкретика, без воды.

ОБЯЗАТЕЛЬНО включи:
1. 📋 ВЕРДИКТ - четкий вывод о достоверности утверждения
2. 🎯 ОСНОВНЫЕ ВЫВОДЫ - ключевые результаты проверки
3. 📚 ДОКАЗАТЕЛЬСТВА - конкретные факты, подтверждающие или опровергающие
4. ⚠️ ВАЖНЫЕ ОГОВОРКИ - нюансы и ограничения в выводах
5. 🔍 МЕТОДОЛОГИЯ - краткое описание процесса проверки
6. 📊 УРОВЕНЬ УВЕРЕННОСТИ - оценка надежности заключения
7. 🎯 РЕКОМЕНДАЦИИ - как читателю лучше оценить информацию

СТРУКТУРА ЗАКЛЮЧЕНИЯ:
- Краткий вердикт в начале: 1 предложение, без вводных вроде «по нашему мнению»
- Детальное обоснование
- Ссылки на ключевые источники
- Практические рекомендации

ФОРМАТ ОТВЕТА (строго на русском языке, популярное изложение):
- Короткие абзацы и списки
- Конкретные формулировки без двусмысленности, избегай слов «в целом», «скорее»
- Ссылки на источники в формате [Название](URL)
- Практические рекомендации для читателя
- Без лишних вступлений
- Не выводи проценты уверенности в первой строке; используй качественную шкалу: высокая/средняя/низкая"""
            },
            {
                "role": "user",
                "content": f"Сформулируй финальное заключение для утверждения: {statement}\n\nКритический анализ: {critical_analysis.get('verification', '')}"
            }
        ]
        
        result = await self._make_request(messages, max_tokens=3000)
        return {"verdict": result, "timestamp": datetime.now().isoformat()}

    def _determine_verification_level(self, final_verdict: Dict) -> str:
        """Определяет уровень верификации на основе финального заключения"""
        verdict_text = final_verdict.get("verdict", "").lower()
        
        if any(word in verdict_text for word in ["подтверждено", "истинно", "верно", "достоверно"]):
            return "✅ ПОДТВЕРЖДЕНО"
        elif any(word in verdict_text for word in ["частично", "отчасти", "некоторые"]):
            return "⚠️ ЧАСТИЧНО ПОДТВЕРЖДЕНО"
        elif any(word in verdict_text for word in ["опровергнуто", "ложно", "неверно", "недостоверно"]):
            return "❌ ОПРОВЕРГНУТО"
        elif any(word in verdict_text for word in ["не удалось", "недостаточно", "неопределенно"]):
            return "❓ НЕ УДАЛОСЬ ПРОВЕРИТЬ"
        else:
            return "🔄 ТРЕБУЕТ ОБНОВЛЕНИЯ"

    def _adjust_verification_with_confidence(self, level: str, confidence: float, final_verdict: Dict) -> str:
        """Корректирует уровень верификации с учётом уверенности.
        Пороговая логика:
        - >= 0.70: уровень не понижается
        - 0.40–0.69: максимум ⚠️ ЧАСТИЧНО ПОДТВЕРЖДЕНО (если не опровергнуто)
        - < 0.40: ❓ НЕ УДАЛОСЬ ПРОВЕРИТЬ (если не опровергнуто)
        Опровержение приоритетнее и не повышается.
        """
        # Если явное опровержение — не повышаем и не понижаем выше него
        if level == "❌ ОПРОВЕРГНУТО":
            return level

        if confidence >= 0.70:
            return level
        if 0.40 <= confidence < 0.70:
            # Не выше частичного подтверждения
            if level == "✅ ПОДТВЕРЖДЕНО":
                return "⚠️ ЧАСТИЧНО ПОДТВЕРЖДЕНО"
            return level
        # < 0.40
        if level == "✅ ПОДТВЕРЖДЕНО" or level == "⚠️ ЧАСТИЧНО ПОДТВЕРЖДЕНО" or level == "🔄 ТРЕБУЕТ ОБНОВЛЕНИЯ":
            return "❓ НЕ УДАЛОСЬ ПРОВЕРИТЬ"
        return level

    def _calculate_confidence_score(self, critical_analysis: Dict) -> float:
        """Рассчитывает уровень уверенности в заключении (0.0 - 1.0)"""
        verification_text = critical_analysis.get("verification", "").lower()
        
        # Факторы, повышающие уверенность
        confidence_boosters = [
            "множественные источники", "независимые источники", "официальные данные",
            "академические исследования", "статистические данные", "экспертные мнения"
        ]
        
        # Факторы, снижающие уверенность
        confidence_reducers = [
            "противоречия", "недостаточно данных", "предвзятость", "устаревшая информация",
            "единичный источник", "неофициальные данные"
        ]
        
        boost_score = sum(1 for booster in confidence_boosters if booster in verification_text)
        reduce_score = sum(1 for reducer in confidence_reducers if reducer in verification_text)
        
        base_score = 0.5
        final_score = base_score + (boost_score * 0.1) - (reduce_score * 0.15)
        
        return max(0.0, min(1.0, final_score))

    def _generate_recommendations(self, final_verdict: Dict) -> List[str]:
        """Генерирует рекомендации для читателя"""
        verdict_text = final_verdict.get("verdict", "").lower()
        recommendations = []
        
        if "противоречия" in verdict_text or "разные мнения" in verdict_text:
            recommendations.append("⚠️ Обратите внимание на противоречия в источниках")
        
        if "устаревшая" in verdict_text or "изменилась" in verdict_text:
            recommendations.append("🔄 Проверьте актуальность информации")
        
        if "предвзятость" in verdict_text or "заинтересованная сторона" in verdict_text:
            recommendations.append("🎯 Учитывайте возможную предвзятость источников")
        
        if "недостаточно данных" in verdict_text:
            recommendations.append("📊 Ищите дополнительные источники для полной картины")
        
        recommendations.append("🔍 Всегда проверяйте информацию по нескольким независимым источникам")
        recommendations.append("📚 Отдавайте предпочтение академическим и официальным источникам")
        
        return recommendations

    def _count_academic_sources_in_analysis(self, source_investigation: Dict, critical_analysis: Dict) -> int:
        """Подсчитывает количество академических источников в анализе"""
        from services.source_validator_service import SourceValidatorService
        
        validator = SourceValidatorService()
        
        # Извлекаем источники из текста анализа
        sources_text = source_investigation.get('sources', '') + ' ' + critical_analysis.get('verification', '')
        sources = validator.extract_sources_from_text(sources_text)
        
        # Подсчитываем академические источники
        return validator.count_academic_sources(sources)

    async def _make_request(self, messages: list, max_tokens: int = 4000) -> str:
        """Выполняет запрос к Perplexity API с улучшенной обработкой ошибок"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "stream": False
        }
        
        timeout = aiohttp.ClientTimeout(total=300, connect=30, sock_read=240)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data["choices"][0]["message"]["content"]
                        logger.info(f"Получен ответ от API: {len(result)} символов")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка API {response.status}: {error_text}")
                        return f"❌ Ошибка API: {response.status}"
        except asyncio.TimeoutError:
            logger.error("Таймаут при запросе к API")
            return "❌ Ошибка: превышено время ожидания ответа"
        except Exception as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return f"❌ Ошибка подключения: {str(e)}"

    async def analyze_article_professionally(self, url: str) -> Dict:
        """
        Профессиональный анализ статьи с многоуровневой проверкой
        """
        logger.info(f"Начинаем профессиональный анализ статьи: {url}")
        # Оценка надежности издания (домен статьи)
        outlet_info = ""
        try:
            _validator = SourceValidatorService()
            _domain = _validator.extract_domain(url)
            _score = _validator.calculate_reliability_score(url)
            _advice = _validator.get_source_quality_advice(url)
            outlet_info = f"{_domain} — {(_score):.2f}; {_advice}"
        except Exception:
            pass
        
        # Этап 1: Анализ содержания статьи
        content_analysis = await self._analyze_article_content(url)
        
        # Этап 2: Проверка фактов из статьи
        fact_verification = await self._verify_article_facts(url, content_analysis)

        # Доп. этап: Поиск манипуляций/риторики в статье
        article_manipulation = await self._detect_article_manipulation(url, content_analysis, fact_verification)
        
        # Этап 3: Оценка качества источников
        source_evaluation = await self._evaluate_article_sources(url, fact_verification)
        
        # Этап 4: Формирование заключения
        final_assessment = await self._form_article_assessment(url, source_evaluation)
        
        return {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "outlet_reliability": outlet_info,
            "content_analysis": content_analysis,
            "fact_verification": fact_verification,
            "source_evaluation": source_evaluation,
            "manipulation_analysis": article_manipulation,
            "final_assessment": final_assessment,
            "overall_rating": self._calculate_article_rating(final_assessment),
            "recommendations": self._generate_article_recommendations(final_assessment)
        }

    async def _analyze_article_content(self, url: str) -> Dict:
        """Анализ содержания статьи"""
        # Пытаемся заранее извлечь текст статьи (полезно для Dzen и динамических сайтов)
        extracted_text = await self._prefetch_article_text(url)
        text_hint = ""
        if extracted_text and len(extracted_text) > 500:
            # Обрезаем до разумного размера, чтобы не переполнить контекст
            snippet = extracted_text[:8000]
            text_hint = f"\n\nТекст статьи (извлечён автоматически):\n{snippet}"

        messages = [
            {
                "role": "system",
                "content": """Ты профессиональный аналитик СМИ. Пиши в стиле executive summary (McKinsey/BCG): деловой тон, ясность, конкретика.

ОБЯЗАТЕЛЬНО проанализируй:
1. 📋 ОСНОВНАЯ ТЕМА - что является центральной темой статьи
2. 🎯 КЛЮЧЕВЫЕ УТВЕРЖДЕНИЯ - выдели все проверяемые факты и утверждения
3. 📊 СТАТИСТИКА И ДАННЫЕ - найди все цифры, проценты, даты
4. 👥 УЧАСТНИКИ - определи всех упомянутых лиц и организаций
5. 🔍 ИСТОЧНИКИ В СТАТЬЕ - найди все ссылки и цитаты; для цитат/пересказов укажи первичность/вторичность и отметь те, что надо трассировать до первоисточника
6. ⚠️ ПОТЕНЦИАЛЬНЫЕ ПРОБЛЕМЫ - выяви возможные искажения или предвзятость
7. 📈 СТРУКТУРА ПОДАЧИ - оцени логику изложения и аргументацию
 
ФОРМАТ ОТВЕТА (строго на русском языке, популярное изложение):
- Короткие предложения и списки, без профессионального жаргона
- Структурированный анализ по разделам
- Список всех проверяемых утверждений
- Выделение ключевых фактов и данных
- Предварительная оценка качества подачи
 - Не добавляй вступления о методологии и дисклеймеры
 - Первое предложение — четкий вывод по статье (1 фраза), без слов «в целом», «скорее»
 - Явно выдели раздел «Риски и ограничения»: актуальность данных, пробелы в источниках, предвзятость, противоречия"""
            },
            {
                "role": "user",
                "content": f"Проанализируй содержание этой статьи: {url}{text_hint}\n\nВАЖНО: Прочитай именно эту статью, а не похожие материалы. Проведи полный анализ содержания."
            }
        ]
        
        result = await self._make_request(messages, max_tokens=3000)
        return {"content_analysis": result, "timestamp": datetime.now().isoformat()}

    async def _prefetch_article_text(self, url: str) -> str:
        """Пытается получить читаемый текст страницы. Без внешних зависимостей.
        Сначала пробуем через r.jina.ai (readability-прокси), затем напрямую.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_read=15)
        candidates = []
        try:
            # Прокси-просмотр читаемого текста
            if url.startswith("http://"):
                candidates.append(f"https://r.jina.ai/{url}")
            elif url.startswith("https://"):
                candidates.append(f"https://r.jina.ai/http://{url[8:]}")
                candidates.append(f"https://r.jina.ai/https://{url[8:]}")
            else:
                candidates.append(f"https://r.jina.ai/http://{url}")
            # Оригинальная страница как fallback
            candidates.append(url)

            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                for u in candidates:
                    try:
                        async with session.get(u) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                # Фильтруем слишком короткие/шаблонные ответы
                                if text and len(text.strip()) > 300:
                                    return text
                    except Exception:
                        continue
        except Exception:
            pass
        return ""

    async def _verify_article_facts(self, url: str, content_analysis: Dict) -> Dict:
        """Проверка фактов из статьи"""
        messages = [
            {
                "role": "system",
                "content": """Ты эксперт по верификации фактов. Пиши сжато, в стиле консультантов (McKinsey/BCG): четкие формулировки, минимум воды.

КРИТИЧЕСКИ ВАЖНО:
1. 🔍 ВЕРИФИКАЦИЯ КАЖДОГО ФАКТА - проверь каждое утверждение отдельно
2. 📚 НЕЗАВИСИМЫЕ ИСТОЧНИКИ - найди подтверждения в независимых источниках
3. 📊 ПРОВЕРКА СТАТИСТИКИ - верифицируй все цифры и данные
4. 👥 ПРОВЕРКА ПЕРСОНАЛИЙ - подтверди информацию о людях и организациях
5. 📅 ПРОВЕРКА ДАТ И СОБЫТИЙ - верифицируй хронологию
6. ⚖️ БАЛАНС МНЕНИЙ - найди альтернативные точки зрения
7. 🎯 ВЫЯВЛЕНИЕ ОШИБОК - определи неточности или искажения

ПРИОРИТЕТЫ ИСТОЧНИКОВ:
- Официальные документы и отчеты
- Академические исследования
- Международные организации
- Репутационные СМИ
- Экспертные мнения

ФОРМАТ ОТВЕТА (строго на русском языке, популярное изложение):
- Короткие пункты для каждого факта (1–2 предложения)
- Ссылки на источники верификации (формат [Название](URL))
- Ясно отмечай: подтверждено/не подтверждено/требует проверки
- Без методологических вступлений
- Начинай с краткого тезиса-вывода (1 предложение), без слов «в целом», «скорее»"""
            },
            {
                "role": "user",
                "content": f"Проверь все факты из этой статьи: {url}\n\nАнализ содержания: {content_analysis.get('content_analysis', '')}"
            }
        ]
        
        result = await self._make_request(messages, max_tokens=4000)
        return {"fact_verification": result, "timestamp": datetime.now().isoformat()}

    async def _detect_article_manipulation(self, url: str, content_analysis: Dict, fact_verification: Dict) -> Dict:
        """Определяет манипуляции в самой статье (подача, заголовки, язык, логические ошибки)."""
        messages = [
            {
                "role": "system",
                "content": """Ты эксперт по медиаграмотности. Найди в статье признаки манипуляции и риторические приемы.

ПРОВЕРЬ:
- эмоционально окрашенные формулировки, ярлыки, демонизацию
- соломенное чучело, ложная дилемма, ложная эквиваленция, cherry-picking
- whataboutism, ad hominem, апелляция к большинству/авторитету
- манипуляции статистикой, неопределенные источники
- кликбейтный заголовок, фрейминг

ФОРМАТ (строго на русском):
- Список приемов (название → объяснение → цитата/пересказ → степень влияния)
- Общая оценка манипулятивности (низкая/средняя/высокая)
- Рекомендации для читателя"""
            },
            {
                "role": "user",
                "content": f"Проанализируй манипуляции в статье: {url}\n\nАнализ содержания: {content_analysis.get('content_analysis','')}\n\nПроверка фактов: {fact_verification.get('fact_verification','')}"
            }
        ]
        result = await self._make_request(messages, max_tokens=2000)
        return {"manipulation": result, "timestamp": datetime.now().isoformat()}

    async def _evaluate_article_sources(self, url: str, fact_verification: Dict) -> Dict:
        """Оценка качества источников статьи"""
        messages = [
            {
                "role": "system",
                "content": """Ты эксперт по оценке качества источников. Твоя задача - оценить надежность и качество всех источников, использованных в статье.

ОБЯЗАТЕЛЬНО оцени:
1. 📚 КАТЕГОРИЗАЦИЯ ИСТОЧНИКОВ - раздели по типам и надежности
2. 🎯 ОЦЕНКА КАЧЕСТВА - определи уровень достоверности каждого источника
3. ⚖️ БАЛАНС ИСТОЧНИКОВ - проанализируй разнообразие точек зрения
4. 🔍 НЕЗАВИСИМОСТЬ - оцени независимость источников от темы
5. 📊 АКТУАЛЬНОСТЬ - проверь свежесть информации
6. ⚠️ ПРЕДВЗЯТОСТЬ - выяви возможные предвзятости
7. 🎯 ПОКРЫТИЕ ТЕМЫ - оцени полноту освещения вопроса

КРИТЕРИИ ОЦЕНКИ:
- Научная обоснованность
- Репутация источника
- Независимость от темы
- Актуальность информации
- Качество аргументации

ОБЯЗАТЕЛЬНО создай таблицу в формате:
| Источник | Оценка | Категория |
|----------|--------|-----------|
| Название источника | 0.85 | Надежный |
| Другой источник | 0.60 | Средней надежности |

ШКАЛА ОЦЕНОК:
- 0.9-1.0: Высоконадежный (академические, официальные)
- 0.7-0.8: Надежный (проверенные СМИ)
- 0.5-0.6: Средней надежности (региональные СМИ)
- 0.3-0.4: Низкой надежности (сомнительные источники)
- 0.0-0.2: Ненадежный (фейковые, предвзятые)

ФОРМАТ ОТВЕТА (строго на русском языке):
- Таблица источников с оценками
- Детальная оценка каждого источника с ссылками [1], [2], [3] и т.д.
- Общая оценка качества источников
- Рекомендации по улучшению
- Выводы о надежности статьи

ВАЖНО: Используй ссылки в формате [1], [2], [3] для указания на источники в таблице."""
            },
            {
                "role": "user",
                "content": f"Оцени качество источников в этой статье: {url}\n\nПроверка фактов: {fact_verification.get('fact_verification', '')}"
            }
        ]
        
        result = await self._make_request(messages, max_tokens=3000)
        return {"source_evaluation": result, "timestamp": datetime.now().isoformat()}

    async def _form_article_assessment(self, url: str, source_evaluation: Dict) -> Dict:
        """Формирование итоговой оценки статьи"""
        messages = [
            {
                "role": "system",
                "content": """Ты главный редактор фактчекингового агентства. Твоя задача - дать итоговую оценку статьи на основе проведенного анализа.

ОБЯЗАТЕЛЬНО включи:
1. 📋 ОБЩАЯ ОЦЕНКА - общий вердикт о качестве статьи
2. 🎯 ДОСТОВЕРНОСТЬ - оценка надежности информации
3. 📚 КАЧЕСТВО ИСТОЧНИКОВ - оценка использованных источников
4. ⚖️ ОБЪЕКТИВНОСТЬ - оценка беспристрастности подачи
5. 🔍 ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ - конкретные недостатки и ошибки
6. ✅ СИЛЬНЫЕ СТОРОНЫ - что сделано хорошо
7. 🎯 РЕКОМЕНДАЦИИ - как читателю лучше оценить статью

СТРУКТУРА ОЦЕНКИ:
- Краткий вердикт в начале
- Детальное обоснование
- Конкретные примеры
- Практические рекомендации

ФОРМАТ ОТВЕТА (строго на русском языке):
- Четкая структура с заголовками
- Конкретные выводы и оценки
- Ссылки на источники верификации
- Практические советы для читателя"""
            },
            {
                "role": "user",
                "content": f"Дай итоговую оценку этой статьи: {url}\n\nОценка источников: {source_evaluation.get('source_evaluation', '')}"
            }
        ]
        
        result = await self._make_request(messages, max_tokens=3000)
        return {"assessment": result, "timestamp": datetime.now().isoformat()}

    def _calculate_article_rating(self, final_assessment: Dict) -> str:
        """Рассчитывает общий рейтинг статьи"""
        assessment_text = final_assessment.get("assessment", "").lower()
        
        if any(word in assessment_text for word in ["высокое качество", "достоверно", "надежно", "объективно"]):
            return "🟢 ВЫСОКОЕ КАЧЕСТВО"
        elif any(word in assessment_text for word in ["хорошее качество", "в целом достоверно", "приемлемо"]):
            return "🟡 ХОРОШЕЕ КАЧЕСТВО"
        elif any(word in assessment_text for word in ["среднее качество", "частично достоверно", "требует осторожности"]):
            return "🟠 СРЕДНЕЕ КАЧЕСТВО"
        elif any(word in assessment_text for word in ["низкое качество", "ненадежно", "предвзято"]):
            return "🔴 НИЗКОЕ КАЧЕСТВО"
        else:
            return "⚪ ТРЕБУЕТ ДОПОЛНИТЕЛЬНОЙ ПРОВЕРКИ"

    def _generate_article_recommendations(self, final_assessment: Dict) -> List[str]:
        """Генерирует рекомендации по статье"""
        assessment_text = final_assessment.get("assessment", "").lower()
        recommendations = []
        
        if "предвзятость" in assessment_text or "односторонне" in assessment_text:
            recommendations.append("⚠️ Учитывайте возможную предвзятость в подаче")
        
        if "устаревшая" in assessment_text or "неактуально" in assessment_text:
            recommendations.append("🔄 Проверьте актуальность информации")
        
        if "недостаточно источников" in assessment_text:
            recommendations.append("📚 Ищите дополнительные источники для полной картины")
        
        if "статистика" in assessment_text and "проверить" in assessment_text:
            recommendations.append("📊 Верифицируйте статистические данные")
        
        recommendations.append("🔍 Всегда проверяйте информацию по нескольким независимым источникам")
        recommendations.append("📚 Отдавайте предпочтение академическим и официальным источникам")
        
        return recommendations
