import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifier import service  # noqa: E402
from verifier.format import to_dict, to_telegram_text  # noqa: E402

pytestmark = pytest.mark.asyncio


def _raw(data, citations=None, fence=False):
    content = json.dumps(data, ensure_ascii=False)
    if fence:
        content = f"Вот ответ:\n```json\n{content}\n```"
    out = {"choices": [{"message": {"content": content}}]}
    if citations:
        out["citations"] = citations
    return out


GOOD = {
    "verdict": "false", "confidence": 85, "confidence_reason": "источники согласны",
    "explanation": "Это неправда.",
    "sources": [
        {"url": "https://ria.ru/a", "title": "РИА", "quote": "q", "date": "2026-01-01"},
        {"url": "https://reuters.com/b", "title": "Reuters", "quote": "q", "date": "2026-01-02"},
        {"url": "https://dead.example/c", "title": "Dead", "quote": "", "date": ""},
    ],
}


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "CACHE_DB", str(tmp_path / "cache.db"))
    monkeypatch.delenv("GOOGLE_FACTCHECK_API_KEY", raising=False)

    async def check(session, url):
        return "dead" not in url
    monkeypatch.setattr(service, "_check_url", check)


async def test_parses_fenced_json_and_citations(monkeypatch):
    async def fake(claim):
        return _raw(GOOD, citations=["https://reuters.com/b", "https://bbc.com/x"], fence=True)
    monkeypatch.setattr(service, "_call_perplexity", fake)

    v = await service.verify("  Луна   сделана из сыра ")
    assert v.claim == "Луна сделана из сыра"
    assert v.verdict == "false" and v.confidence == 85
    urls = [s.url for s in v.sources]
    assert "https://dead.example/c" not in urls and "https://bbc.com/x" in urls
    assert v.sources == sorted(v.sources, key=lambda s: s.score, reverse=True)
    assert v.sources[0].domain and v.sources[0].title
    text = to_telegram_text(v)
    assert text.startswith("🟥 ЛОЖЬ · уверенность 85 %") and "1. " in text
    assert to_dict(v)["label"] == "Ложь"


async def test_regex_fallback_for_json():
    data = service._parse_json('Ответ: {"verdict": "true", "confidence": 50} спасибо')
    assert data["verdict"] == "true"


async def test_confidence_capped_when_few_live_sources(monkeypatch):
    data = dict(GOOD, sources=[GOOD["sources"][0], GOOD["sources"][2]])

    async def fake(claim):
        return _raw(data)
    monkeypatch.setattr(service, "_call_perplexity", fake)

    v = await service.verify("что-то")
    assert len(v.sources) == 1 and v.confidence == 40
    assert "мало живых" in v.confidence_reason


async def test_unverifiable_on_exception(monkeypatch):
    async def boom(claim):
        raise RuntimeError("Perplexity HTTP 500")
    monkeypatch.setattr(service, "_call_perplexity", boom)

    v = await service.verify("что-то")
    assert v.verdict == "unverifiable" and v.confidence == 0
    assert "Perplexity HTTP 500" in v.explanation
    assert "⬜" in to_telegram_text(v)


async def test_cache_hit(monkeypatch):
    calls = []

    async def fake(claim):
        calls.append(claim)
        return _raw(GOOD)
    monkeypatch.setattr(service, "_call_perplexity", fake)

    v1 = await service.verify("Кэш тест")
    v2 = await service.verify("кэш  тест")
    assert len(calls) == 1
    assert not v1.cached and v2.cached
    assert v2.verdict == v1.verdict and [s.url for s in v2.sources] == [s.url for s in v1.sources]


async def test_web_endpoints(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from verifier.web import app

    async def fake(claim):
        return _raw(GOOD)
    monkeypatch.setattr(service, "_call_perplexity", fake)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/health")).status_code == 200
        assert "textarea" in (await c.get("/")).text
        r = await c.post("/api/verify", json={"claim": "x"})
        assert r.status_code == 200 and r.json()["label"] == "Ложь"
        assert (await c.post("/api/verify", json={"claim": ""})).status_code == 400
