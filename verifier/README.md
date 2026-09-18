# verifier — мгновенная проверка утверждений

Минимальный MVP из `docs/market_research.md` §5: одно текстовое поле (утверждение или ссылка) →
один вызов Perplexity `sonar` → проверка, что ссылки живые (HEAD/GET, 2 с) → вердикт
с калиброванной уверенностью и 3–5 источниками. Ответы кэшируются в SQLite на 7 дней.

## Переменные окружения
- `PERPLEXITY_API_KEY` — обязательно (берётся из `app_config.Config` / `.env`).
- `GOOGLE_FACTCHECK_API_KEY` — опционально; включает блок «Уже проверяли» (Google Fact Check Tools, `languageCode=ru`).
- `VERIFIER_CACHE_DB` — путь к файлу кэша (по умолчанию `verifier_cache.db`).

## Запуск
```bash
pip install -r requirements.txt
uvicorn verifier.web:app --host 0.0.0.0 --port 8000   # веб: /  /api/verify  /health
python -m verifier.cli "Пингвины живут на Северном полюсе"  # CLI
```
`POST /api/verify` принимает `{"claim": "..."}` и возвращает JSON (`verdict`, `confidence`,
`explanation`, `sources`, `existing_factchecks`, `label`, `emoji`).

## Подключение к Telegram-боту (python-telegram-bot 20.x)
```python
from telegram.ext import MessageHandler, filters
from verifier import verify, to_telegram_text

async def on_text(update, context):
    verdict = await verify(update.message.text)
    await update.message.reply_text(to_telegram_text(verdict), disable_web_page_preview=True)

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
```

## Стоимость
Один запрос `sonar` с `search_context_size=low` ≈ $0.005–0.01 (≈ 1 ₽ за проверку);
повторные (кэш) и Google Fact Check — бесплатно. Тесты: `pytest tests/test_verifier.py`.
