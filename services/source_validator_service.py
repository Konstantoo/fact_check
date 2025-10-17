import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse
import aiohttp
import asyncio
import time

class SourceValidatorService:
    """Сервис для валидации и ранжирования источников по надежности"""
    
    def __init__(self):
        # Домены с высокой надежностью (научные, официальные, международные)
        self.high_reliability_domains = {
            # Научные журналы и базы данных (ПРИОРИТЕТ)
            'nature.com', 'science.org', 'pubmed.ncbi.nlm.nih.gov', 'scholar.google.com',
            'arxiv.org', 'jstor.org', 'springer.com', 'wiley.com', 'elsevier.com',
            'cell.com', 'lancet.com', 'nejm.org', 'bmj.com', 'jama.com',
            'plos.org', 'frontiersin.org', 'mdpi.com', 'hindawi.com',
            'academic.oup.com', 'cambridge.org', 'sagepub.com', 'tandfonline.com',
            'researchgate.net', 'academia.edu', 'scholar.google.com',
            
            # Официальные международные организации
            'un.org', 'who.int', 'imf.org', 'worldbank.org', 'oecd.org', 'europa.eu',
            'fda.gov', 'cdc.gov', 'nih.gov', 'nsa.gov', 'cia.gov',
            
            # Международные новостные агентства
            'reuters.com', 'ap.org', 'afp.com', 'bbc.com', 'dw.com', 'france24.com',
            'aljazeera.com',
            
            # Академические институты
            'harvard.edu', 'mit.edu', 'stanford.edu', 'yale.edu', 'princeton.edu',
            'oxford.ac.uk', 'cambridge.ac.uk', 'sorbonne.fr', 'mpg.de',
            
            # Профессиональные издания
            'bloomberg.com', 'wsj.com', 'ft.com', 'economist.com', 'forbes.com',
            'wired.com', 'techcrunch.com', 'venturebeat.com'
        }
        
        # Домены со средней надежностью
        self.medium_reliability_domains = {
            # Региональные новостные издания
            'cnn.com', 'foxnews.com', 'msnbc.com', 'npr.org', 'pbs.org',
            'guardian.com', 'independent.co.uk', 'telegraph.co.uk',
            'lemonde.fr', 'spiegel.de', 'repubblica.it', 'elpais.com',
            
            # Специализированные издания
            'wired.com', 'techcrunch.com', 'venturebeat.com', 'arstechnica.com',
            'theverge.com', 'engadget.com', 'gizmodo.com'
        }
        
        # Домены с потенциальной предвзятостью (анализируй, но предупреждай)
        self.biased_domains = {
            # Государственные СМИ
            'ria.ru', 'tass.ru', 'rt.com', 'sputniknews.com', 'gazeta.ru',
            'lenta.ru', 'rbc.ru', 'interfax.ru', 'kommersant.ru',
            
            # Оппозиционные издания
            'meduza.io', 'currenttime.tv', 'svoboda.org', 'voanews.com', 'rferl.org',
            
            # Партийные издания
            'kremlin.ru', 'government.ru', 'duma.gov.ru'
        }
        
        # Домены с низкой надежностью
        self.low_reliability_domains = {
            'wikipedia.org', 'reddit.com', 'twitter.com', 'facebook.com',
            'instagram.com', 'tiktok.com', 'youtube.com', 'blogspot.com',
            'wordpress.com', 'medium.com', 'substack.com'
        }

        # Признаки и категории для динамической оценки
        self.academic_domain_suffixes = (".edu", ".ac.uk", ".ac.", ".edu.")
        self.academic_indicators = {
            "doi.org", "pubmed", "ncbi.nlm.nih.gov", "arxiv.org", "springer.com",
            "wiley.com", "sciencedirect.com", "nature.com", "science.org", "jstor.org",
            "cell.com", "lancet.com", "nejm.org", "bmj.com", "jama.com", "plos.org",
            "frontiersin.org", "mdpi.com", "hindawi.com", "academic.oup.com",
            "cambridge.org", "sagepub.com", "tandfonline.com", "researchgate.net",
            "academia.edu", "scholar.google.com"
        }
        
        # Индикаторы whitepaper и технических отчетов
        self.whitepaper_indicators = {
            "/whitepaper", "/white-paper", "/technical-report", "/research-report",
            "/study", "/analysis", "/findings", "/methodology", "/results",
            "whitepaper", "white paper", "technical report", "research report"
        }
        self.reputable_media_indicators = {
            "reuters.com", "ap.org", "bbc.com", "ft.com", "economist.com", "bloomberg.com",
            "wsj.com"
        }
        self.blog_social_indicators = {
            "medium.com", "substack.com", "wordpress.com", "blogspot.com", "reddit.com",
            "twitter.com", "x.com", "facebook.com", "t.me", "telegram.me", "instagram.com",
            "vk.com", "youtube.com"
        }
        self.interested_party_indicators = {
            "/press", "/press-releases", "/newsroom", "/media/", "prnewswire.com", "businesswire.com",
            "about.", "/about/", "/our-", "/investors"
        }

        # In-memory TTL-кэш проверок URL на 10 минут
        self._check_cache: Dict[str, Tuple[bool, float]] = {}
        self._cache_ttl_sec = 600.0

    def extract_domain(self, url: str) -> str:
        """Извлекает домен из URL"""
        try:
            # Нормализуем URL: убираем якоря и UTM-параметры
            parsed = urlparse(url.split('#')[0])
            domain = parsed.netloc.lower()
            # Убираем www.
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""

    def classify_source(self, url: str) -> str:
        """Возвращает категорию источника"""
        domain = self.extract_domain(url)
        url_lower = url.lower()

        # Приоритет: академические источники и whitepaper
        if domain.endswith(self.academic_domain_suffixes) or any(ind in url_lower for ind in self.academic_indicators):
            return "academic"
        if any(ind in url_lower for ind in self.whitepaper_indicators):
            return "whitepaper"
        if domain.endswith(".gov") or ".gov." in domain:
            return "official_gov"
        if domain in self.reputable_media_indicators:
            return "reputable_media"
        if any(ind in domain or ind in url_lower for ind in self.blog_social_indicators):
            return "blog_social"
        if any(ind in url_lower for ind in self.interested_party_indicators):
            return "interested_party"
        if any(k in domain for k in (".org", "foundation", "institute")) and not domain.endswith(".gov"):
            return "think_tank_ngo"
        return "unknown"

    def calculate_reliability_score(self, url: str) -> float:
        """Динамическая оценка надежности (0.0 - 1.0)"""
        domain = self.extract_domain(url)
        if not domain:
            return 0.1

        # Базовая оценка по справочнику доменов
        if domain in self.high_reliability_domains:
            base = 0.9
        elif domain in self.medium_reliability_domains:
            base = 0.7
        elif domain in self.biased_domains:
            base = 0.4
        elif domain in self.low_reliability_domains:
            base = 0.2
        else:
            base = 0.5

        # Коррекция на категорию источника
        category = self.classify_source(url)
        weight = {
            "academic": 1.3,  # Повышенный приоритет для академических источников
            "whitepaper": 1.25,  # Высокий приоритет для whitepaper
            "official_gov": 1.15,
            "reputable_media": 1.05,
            "think_tank_ngo": 1.0,
            "unknown": 1.0,
            "blog_social": 0.7,
            "interested_party": 0.5,
        }.get(category, 1.0)

        score = max(0.0, min(1.0, base * weight))
        return score

    def get_source_quality_advice(self, url: str) -> str:
        """Возвращает рекомендацию по качеству источника"""
        score = self.calculate_reliability_score(url)
        category = self.classify_source(url)

        label = {
            "academic": "🎓 Академический/научный источник",
            "whitepaper": "📄 Whitepaper/технический отчет",
            "official_gov": "🏛️ Официальный источник",
            "reputable_media": "📰 Репутационное СМИ",
            "think_tank_ngo": "🏷️ Исследовательский центр/НКО",
            "blog_social": "💬 Блог/социальные сети",
            "interested_party": "⚠️ Заинтересованная сторона/PR",
            "unknown": "ℹ️ Неопределённый тип",
        }.get(category, "ℹ️ Неопределённый тип")

        if score >= 0.8:
            return f"✅ Высокая надежность — {label}"
        elif score >= 0.6:
            return f"⚠️ Средняя надежность — {label}"
        elif score >= 0.4:
            return f"⚠️ Возможная предвзятость — {label}"
        else:
            return f"❌ Низкая надежность — {label}"

    def rank_sources(self, sources: List[str]) -> List[Tuple[str, float, str, str]]:
        """Ранжирует источники по надежности с категорией"""
        ranked = []
        for source in sources:
            score = self.calculate_reliability_score(source)
            advice = self.get_source_quality_advice(source)
            category = self.classify_source(source)
            ranked.append((source, score, advice, category))
        
        # Сортируем по убыванию надежности
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def extract_sources_from_text(self, text: str) -> List[str]:
        """Извлекает URL из текста"""
        url_pattern = r'https?://[^\s\)\]\}]+'
        urls = re.findall(url_pattern, text)
        return urls

    def extract_markdown_links(self, text: str) -> List[Tuple[str, str]]:
        """Извлекает Markdown-ссылки вида [Название](URL)"""
        pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\)\s]+)\)")
        return pattern.findall(text)

    async def _check_url(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Проверяет, что URL доступен (2xx/3xx) с таймаутом и редиректами"""
        try:
            # Кэш
            now = time.monotonic()
            cached = self._check_cache.get(url)
            if cached and (now - cached[1]) < self._cache_ttl_sec:
                return cached[0]
            timeout = aiohttp.ClientTimeout(total=12)
            # Сначала HEAD
            async with session.head(url, allow_redirects=True, timeout=timeout) as resp:
                if 200 <= resp.status < 400:
                    self._check_cache[url] = (True, time.monotonic())
                    return True
            # Затем GET как запасной вариант
            async with session.get(url, allow_redirects=True, timeout=timeout) as resp:
                ok = 200 <= resp.status < 400
                self._check_cache[url] = (ok, time.monotonic())
                return ok
        except Exception:
            self._check_cache[url] = (False, time.monotonic())
            return False

    async def validate_and_annotate(self, text: str) -> str:
        """Проверяет ссылки, ранжирует и добавляет рекомендации"""
        markdown_links = self.extract_markdown_links(text)
        urls = [u for _, u in markdown_links]
        if not urls:
            # Попробуем голые URL
            urls = self.extract_sources_from_text(text)
            markdown_links = [(u, u) for u in urls]

        if not urls:
            return text

        # По умолчанию используем проверку SSL; можно отключать через env при необходимости
        connector = aiohttp.TCPConnector(ssl=None)
        valid: List[Tuple[str, str]] = []
        invalid_count = 0
        semaphore = asyncio.Semaphore(5)
        start_ts = time.monotonic()
        async def _bounded_check(session: aiohttp.ClientSession, u: str):
            async with semaphore:
                return await self._check_url(session, u)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = [_bounded_check(session, url) for _, url in markdown_links]
                results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=12)
        except Exception:
            results = [False] * len(markdown_links)

        for (title, url), ok in zip(markdown_links, results):
            ok_bool = bool(ok) and not isinstance(ok, Exception)
            if ok_bool:
                valid.append((title, url))
            else:
                invalid_count += 1

        if not valid:
            # Нечего добавлять
            return text + "\n\n⚠️ Не удалось подтвердить доступность источников в ответе."

        # Ранжируем валидные источники
        ranked = self.rank_sources([url for _, url in valid])
        url_to_title = {url: title for title, url in valid}

        lines = ["\n\n🔗 Проверенные источники (доступны):"]
        for (url, score, advice, category) in ranked[:8]:
            title = url_to_title.get(url, url)
            lines.append(f"• [{title}]({url}) — {advice} (оценка: {score:.2f})")
        if invalid_count:
            lines.append(f"\n⚠️ Недоступных/ошибочных ссылок: {invalid_count}")

        # Рекомендации по улучшению и пометки интереса
        analysis = self.analyze_source_reliability("\n".join(u for _, u in valid))
        if analysis.get("recommendations"):
            lines.append("\n🧭 Рекомендации по источникам:")
            for rec in analysis["recommendations"][:5]:
                lines.append(f"• {rec}")

        # Помечаем потенциальный конфликт интересов
        for (title, url) in valid:
            if any(ind in url.lower() for ind in self.interested_party_indicators):
                lines.append(f"⚠️ Возможный конфликт интересов у источника: [{title}]({url})")

        return text + "\n" + "\n".join(lines)

    async def build_verified_sources_block(
        self,
        text: str,
        min_required: int,
        title: str = "📚 Источники",
        exclude_categories: List[str] | None = None,
        exclude_domains: List[str] | None = None,
        limit: int | None = None,
    ) -> str:
        """Строит блок со списком верифицированных источников, исключая блоги/вики и т.п.

        - min_required: минимальное число ссылок, к которому стремимся
        - exclude_categories: категории, которые исключаем (по classify_source)
        - exclude_domains: домены (substring match), которые исключаем
        - limit: максимум ссылок в выдаче (если None, берем min_required или 20)
        """
        exclude_categories = exclude_categories or ["blog_social"]
        exclude_domains = exclude_domains or ["wikipedia.org"]
        if limit is None:
            limit = max(min_required, 20 if min_required >= 15 else min_required)

        # Извлекаем URL из markdown и plain текста
        md_links = self.extract_markdown_links(text)
        urls = [u for _, u in md_links]
        if not urls:
            urls = self.extract_sources_from_text(text)
        if not urls:
            return f"{title}\n\n⚠️ Не удалось найти источники в тексте."

        # Проверяем доступность URL (параллельно)
        connector = aiohttp.TCPConnector(ssl=None)
        semaphore = asyncio.Semaphore(5)
        async def _bounded_check(session: aiohttp.ClientSession, u: str):
            async with semaphore:
                return await self._check_url(session, u)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = [_bounded_check(session, u) for u in urls]
                results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=12)
        except Exception:
            results = [False] * len(urls)

        valid_urls: List[str] = []
        for u, ok in zip(urls, results):
            if bool(ok) and not isinstance(ok, Exception):
                valid_urls.append(u)

        if not valid_urls:
            return f"{title}\n\n⚠️ Нет доступных источников."

        # Фильтрация по категориям и доменам, ранжирование
        ranked = self.rank_sources(valid_urls)
        filtered: List[tuple[str, float, str, str]] = []
        
        # Сначала добавляем академические источники и whitepaper
        academic_sources = []
        other_sources = []
        
        for (u, score, advice, category) in ranked:
            dom = self.extract_domain(u)
            if category in exclude_categories:
                continue
            if any(ex in dom for ex in exclude_domains):
                continue
            
            if category in ["academic", "whitepaper"]:
                academic_sources.append((u, score, advice, category))
            else:
                other_sources.append((u, score, advice, category))
        
        # Приоритет академическим источникам
        filtered.extend(academic_sources)
        filtered.extend(other_sources)

        # Сбор итогового списка
        out_lines: List[str] = [f"{title}\n"]
        count = 0
        for (u, score, advice, category) in filtered:
            out_lines.append(f"[{count+1}] [{u}]({u}) — {advice} (оценка: {score:.2f})")
            count += 1
            if count >= limit:
                break

        # Подсчитываем академические источники
        academic_count = self.count_academic_sources([u for (u, _, _, _) in filtered[:count]])
        
        if count < min_required:
            out_lines.append(f"\n⚠️ Внимание: найдено {count} проверенных источников, требуется ≥{min_required}.")
        
        if academic_count < 5:
            out_lines.append(f"\n⚠️ Внимание: найдено {academic_count} академических источников, рекомендуется ≥5 для качественной проверки фактов.")

        return "\n".join(out_lines).strip()

    def analyze_source_reliability(self, text: str) -> Dict:
        """Анализирует надежность всех источников в тексте"""
        sources = self.extract_sources_from_text(text)
        if not sources:
            return {
                "sources_found": 0,
                "reliability_analysis": "Источники не найдены",
                "recommendations": []
            }
        
        ranked_sources = self.rank_sources(sources)
        
        # Группируем по уровням надежности
        high_quality = [s for s in ranked_sources if s[1] >= 0.8]
        medium_quality = [s for s in ranked_sources if 0.6 <= s[1] < 0.8]
        biased_sources = [s for s in ranked_sources if 0.4 <= s[1] < 0.6]
        low_quality = [s for s in ranked_sources if s[1] < 0.4]
        
        analysis = f"Найдено источников: {len(sources)}\n"
        analysis += f"Высоконадежных: {len(high_quality)}\n"
        analysis += f"Средней надежности: {len(medium_quality)}\n"
        analysis += f"С потенциальной предвзятостью: {len(biased_sources)}\n"
        analysis += f"Низкой надежности: {len(low_quality)}"
        
        recommendations = []
        if biased_sources:
            recommendations.append("⚠️ Обнаружены источники с потенциальной предвзятостью - анализируй критически")
        if low_quality:
            recommendations.append("❌ Некоторые источники имеют низкую надежность")
        if not high_quality:
            recommendations.append("💡 Рекомендуется добавить академические/официальные источники")

        # Баланс мнений и независимая сторона
        categories_present = {c for (_, _, _, c) in ranked_sources}
        if "interested_party" in categories_present and "academic" not in categories_present and "official_gov" not in categories_present:
            recommendations.append("⚖️ Добавьте независимую сторону: академические/официальные/репутационные источники, не аффилированные с участниками")
        if "blog_social" in categories_present and len(high_quality) < 2:
            recommendations.append("💡 Снизьте долю блогов/соцсетей, добавьте peer-reviewed/официальные отчёты")
        
        return {
            "sources_found": len(sources),
            "reliability_analysis": analysis,
            "ranked_sources": ranked_sources,
            "recommendations": recommendations
        }

    def count_academic_sources(self, sources: List[str]) -> int:
        """Подсчитывает количество академических источников и whitepaper"""
        academic_count = 0
        for source in sources:
            category = self.classify_source(source)
            if category in ["academic", "whitepaper"]:
                academic_count += 1
        return academic_count

    def get_academic_sources(self, sources: List[str]) -> List[Tuple[str, float, str, str]]:
        """Возвращает только академические источники и whitepaper"""
        ranked = self.rank_sources(sources)
        academic_sources = []
        for (url, score, advice, category) in ranked:
            if category in ["academic", "whitepaper"]:
                academic_sources.append((url, score, advice, category))
        return academic_sources
