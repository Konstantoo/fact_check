import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse

class SourceValidatorService:
    """Сервис для валидации и ранжирования источников по надежности"""
    
    def __init__(self):
        # Домены с высокой надежностью (научные, официальные, международные)
        self.high_reliability_domains = {
            # Научные журналы и базы данных
            'nature.com', 'science.org', 'pubmed.ncbi.nlm.nih.gov', 'scholar.google.com',
            'arxiv.org', 'jstor.org', 'springer.com', 'wiley.com', 'elsevier.com',
            
            # Официальные международные организации
            'un.org', 'who.int', 'imf.org', 'worldbank.org', 'oecd.org', 'europa.eu',
            'fda.gov', 'cdc.gov', 'nih.gov', 'nsa.gov', 'cia.gov',
            
            # Международные новостные агентства
            'reuters.com', 'ap.org', 'afp.com', 'bbc.com', 'dw.com', 'france24.com',
            'aljazeera.com', 'dw.com', 'rt.com', 'sputniknews.com',
            
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
            'meduza.io', 'currenttime.tv', 'svoboda.org', 'dw.com',
            'bbc.com', 'voanews.com', 'rferl.org',
            
            # Партийные издания
            'kremlin.ru', 'government.ru', 'duma.gov.ru'
        }
        
        # Домены с низкой надежностью
        self.low_reliability_domains = {
            'wikipedia.org', 'reddit.com', 'twitter.com', 'facebook.com',
            'instagram.com', 'tiktok.com', 'youtube.com', 'blogspot.com',
            'wordpress.com', 'medium.com', 'substack.com'
        }

    def extract_domain(self, url: str) -> str:
        """Извлекает домен из URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Убираем www.
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""

    def calculate_reliability_score(self, url: str) -> float:
        """Рассчитывает оценку надежности источника (0.0 - 1.0)"""
        domain = self.extract_domain(url)
        
        if not domain:
            return 0.1
        
        if domain in self.high_reliability_domains:
            return 0.9
        elif domain in self.medium_reliability_domains:
            return 0.7
        elif domain in self.biased_domains:
            return 0.3  # Анализируем, но предупреждаем
        elif domain in self.low_reliability_domains:
            return 0.1
        else:
            return 0.5  # Неизвестный домен - средняя оценка

    def get_source_quality_advice(self, url: str) -> str:
        """Возвращает рекомендацию по качеству источника"""
        domain = self.extract_domain(url)
        score = self.calculate_reliability_score(url)
        
        if score >= 0.8:
            return "✅ Высоконадежный источник"
        elif score >= 0.6:
            return "⚠️ Источник средней надежности"
        elif score >= 0.3:
            return "⚠️ Источник с потенциальной предвзятостью - анализируй критически"
        else:
            return "❌ Низкая надежность источника"

    def rank_sources(self, sources: List[str]) -> List[Tuple[str, float, str]]:
        """Ранжирует источники по надежности"""
        ranked = []
        for source in sources:
            score = self.calculate_reliability_score(source)
            advice = self.get_source_quality_advice(source)
            ranked.append((source, score, advice))
        
        # Сортируем по убыванию надежности
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def extract_sources_from_text(self, text: str) -> List[str]:
        """Извлекает URL из текста"""
        url_pattern = r'https?://[^\s\)\]\}]+'
        urls = re.findall(url_pattern, text)
        return urls

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
        biased_sources = [s for s in ranked_sources if 0.3 <= s[1] < 0.6]
        low_quality = [s for s in ranked_sources if s[1] < 0.3]
        
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
            recommendations.append("💡 Рекомендуется найти дополнительные высоконадежные источники")
        
        return {
            "sources_found": len(sources),
            "reliability_analysis": analysis,
            "ranked_sources": ranked_sources,
            "recommendations": recommendations
        }
