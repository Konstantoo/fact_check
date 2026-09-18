"""Пайплайн проверки: нормализация -> Perplexity sonar -> живые ссылки -> вердикт."""
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

try:
    from app_config import Config
    PERPLEXITY_API_KEY = Config.PERPLEXITY_API_KEY
except Exception:  # pragma: no cover
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")

from services.source_validator_service import SourceValidatorService

VERDICTS = ("true", "mostly_true", "mixed", "mostly_false", "false", "unverifiable")
MAX_CLAIM_LEN = 1000
CACHE_DB = os.getenv("VERIFIER_CACHE_DB", "verifier_cache.db")
CACHE_TTL = 7 * 24 * 3600
URL_TIMEOUT = 2
URL_CONCURRENCY = 5
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
GOOGLE_FC_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

SYSTEM_PROMPT = (
    "Ты — строгий фактчекер. Проверь утверждение пользователя по свежим и авторитетным "
    "источникам и ответь ТОЛЬКО валидным JSON без пояснений и без markdown:\n"
    '{"verdict": "true|mostly_true|mixed|mostly_false|false|unverifiable", '
    '"confidence": 0-100, "confidence_reason": "почему такая уверенность (кратко)", '
    '"explanation": "одно предложение на русском", '
    '"sources": [{"url": "...", "title": "...", "quote": "...", "date": "YYYY-MM-DD"}]}\n'
    "Правила: 3-5 источников с реальными URL; quote — короткая цитата; если данных нет — "
    "verdict=unverifiable и низкая confidence. Не выдумывай ссылки."
)

_validator = SourceValidatorService()


@dataclass
class Source:
    url: str
    title: str = ""
    quote: str = ""
    date: str = ""
    score: float = 0.0
    domain: str = ""


@dataclass
class FactCheck:
    publisher: str
    rating: str
    url: str


@dataclass
class Verdict:
    claim: str
    verdict: str = "unverifiable"
    confidence: int = 0
    confidence_reason: str = ""
    explanation: str = ""
    sources: List[Source] = field(default_factory=list)
    existing_factchecks: List[FactCheck] = field(default_factory=list)
    cached: bool = False


# ---------- нормализация и извлечение ----------

def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text[:MAX_CLAIM_LEN]


def _is_url(text: str) -> bool:
    return bool(re.fullmatch(r"https?://\S+", text))


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


async def _fetch_page(url: str) -> str:
    """Возвращает 'Заголовок: ...\nТекст: ...' для проверки главного тезиса страницы."""
    timeout = aiohttp.ClientTimeout(total=8)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}) as s:
        async with s.get(url, allow_redirects=True) as resp:
            html = (await resp.read())[:300_000].decode(resp.charset or "utf-8", "ignore")
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    title = _strip_html(m.group(1)) if m else ""
    body = _strip_html(html)[:1500]
    return f"Заголовок: {title}\nТекст: {body}"


# ---------- Perplexity ----------

async def _call_perplexity(claim: str) -> Dict[str, Any]:
    if not PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY не задан")
    payload = {
        "model": "sonar",
        "temperature": 0.1,
        "web_search_options": {"search_context_size": "low"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Утверждение: {claim}"},
        ],
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=40)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.post(PERPLEXITY_URL, headers=headers, json=payload) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Perplexity HTTP {resp.status}: {(await resp.text())[:200]}")
            return await resp.json()


def _parse_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError("В ответе модели нет JSON")
        return json.loads(m.group(0))


def _build_verdict(claim: str, raw: Dict[str, Any]) -> Verdict:
    content = raw["choices"][0]["message"]["content"]
    data = _parse_json(content)
    verdict = str(data.get("verdict", "unverifiable")).lower().strip()
    if verdict not in VERDICTS:
        verdict = "unverifiable"
    try:
        confidence = max(0, min(100, int(float(data.get("confidence", 0)))))
    except (TypeError, ValueError):
        confidence = 0
    sources: List[Source] = []
    seen = set()
    for s in data.get("sources") or []:
        if isinstance(s, dict) and str(s.get("url", "")).startswith("http") and s["url"] not in seen:
            seen.add(s["url"])
            sources.append(Source(url=s["url"], title=str(s.get("title") or ""),
                                  quote=str(s.get("quote") or ""), date=str(s.get("date") or "")))
    for url in raw.get("citations") or []:
        if isinstance(url, str) and url.startswith("http") and url not in seen:
            seen.add(url)
            sources.append(Source(url=url))
    return Verdict(claim=claim, verdict=verdict, confidence=confidence,
                   confidence_reason=str(data.get("confidence_reason") or ""),
                   explanation=str(data.get("explanation") or ""), sources=sources)


# ---------- проверка ссылок ----------

async def _check_url(session: aiohttp.ClientSession, url: str) -> bool:
    """HEAD, затем GET; 2xx/3xx = живая. Отдельно от SourceValidatorService из-за таймаута 2 с."""
    timeout = aiohttp.ClientTimeout(total=URL_TIMEOUT)
    try:
        async with session.head(url, allow_redirects=True, timeout=timeout) as r:
            if 200 <= r.status < 400:
                return True
        async with session.get(url, allow_redirects=True, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


async def _filter_live(sources: List[Source]) -> List[Source]:
    sem = asyncio.Semaphore(URL_CONCURRENCY)
    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
        async def check(src: Source) -> bool:
            async with sem:
                return await _check_url(session, src.url)
        alive = await asyncio.gather(*(check(s) for s in sources))
    live = [s for s, ok in zip(sources, alive) if ok]
    for s in live:
        s.domain = _validator.extract_domain(s.url) or urlparse(s.url).netloc
        s.score = _validator.calculate_reliability_score(s.url)
        s.title = s.title or s.domain
    live.sort(key=lambda s: s.score, reverse=True)
    return live[:5]


# ---------- Google Fact Check ----------

async def _google_factcheck(claim: str) -> List[FactCheck]:
    key = os.getenv("GOOGLE_FACTCHECK_API_KEY", "")
    if not key:
        return []
    params = {"query": claim[:300], "languageCode": "ru", "key": key, "pageSize": 3}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
            async with s.get(GOOGLE_FC_URL, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception:
        return []
    out = []
    for c in data.get("claims") or []:
        for r in c.get("claimReview") or []:
            out.append(FactCheck(publisher=(r.get("publisher") or {}).get("name", "?"),
                                 rating=r.get("textualRating", ""), url=r.get("url", "")))
    return out[:3]


# ---------- кэш ----------

def _cache_key(claim: str) -> str:
    return hashlib.sha256(claim.lower().encode()).hexdigest()


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(CACHE_DB)
    con.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, ts REAL, data TEXT)")
    return con


def _cache_get(claim: str) -> Optional[Verdict]:
    try:
        with _db() as con:
            row = con.execute("SELECT ts, data FROM cache WHERE key=?", (_cache_key(claim),)).fetchone()
        if not row or time.time() - row[0] > CACHE_TTL:
            return None
        d = json.loads(row[1])
        d["sources"] = [Source(**s) for s in d.get("sources", [])]
        d["existing_factchecks"] = [FactCheck(**f) for f in d.get("existing_factchecks", [])]
        return Verdict(**{**d, "cached": True})
    except Exception:
        return None


def _cache_set(v: Verdict) -> None:
    try:
        with _db() as con:
            con.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)",
                        (_cache_key(v.claim), time.time(), json.dumps(asdict(v), ensure_ascii=False)))
    except Exception:
        pass


# ---------- главная функция ----------

async def verify(claim: str) -> Verdict:
    """Проверяет утверждение или ссылку. Никогда не бросает исключений."""
    claim = normalize(claim)
    if not claim:
        return Verdict(claim="", explanation="Пустой запрос.")
    cached = _cache_get(claim)
    if cached:
        return cached
    try:
        query = claim
        if _is_url(claim):
            query = normalize(await _fetch_page(claim))
        raw, factchecks = await asyncio.gather(_call_perplexity(query), _google_factcheck(query))
        v = _build_verdict(claim, raw)
        v.existing_factchecks = factchecks
        v.sources = await _filter_live(v.sources)
        if len(v.sources) < 2:
            v.confidence = min(v.confidence, 40)
            if v.verdict != "unverifiable":
                note = "мало живых независимых источников"
                v.confidence_reason = f"{v.confidence_reason}; {note}" if v.confidence_reason else note
        _cache_set(v)
        return v
    except Exception as e:
        return Verdict(claim=claim, verdict="unverifiable", confidence=0,
                       confidence_reason="ошибка при обращении к сервисам",
                       explanation=f"Не удалось выполнить проверку: {type(e).__name__}: {e}")
