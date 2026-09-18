"""Форматирование вердикта для Telegram и JSON."""
from dataclasses import asdict
from typing import Any, Dict

from .service import Verdict

LABELS = {
    "true": ("🟩", "Правда"),
    "mostly_true": ("🟩", "Скорее правда"),
    "mixed": ("🟨", "Смешанно"),
    "mostly_false": ("🟥", "Скорее ложь"),
    "false": ("🟥", "Ложь"),
    "unverifiable": ("⬜", "Нельзя проверить"),
}


def label(verdict: str) -> tuple:
    return LABELS.get(verdict, LABELS["unverifiable"])


def to_telegram_text(v: Verdict) -> str:
    emoji, name = label(v.verdict)
    claim = v.claim if len(v.claim) <= 200 else v.claim[:197] + "..."
    lines = [f"{emoji} {name.upper()} · уверенность {v.confidence} %", f"Утверждение: «{claim}»"]
    if v.explanation:
        lines.append(f"Почему: {v.explanation}")
    if v.existing_factchecks:
        lines.append("Уже проверяли:")
        lines += [f"• {f.publisher} — {f.rating}\n  {f.url}" for f in v.existing_factchecks]
    if v.sources:
        lines.append("Источники:")
        for i, s in enumerate(v.sources, 1):
            meta = ", ".join(x for x in (s.domain, s.date) if x)
            lines.append(f"{i}. {s.title} — {meta}\n   {s.url}")
    if v.confidence_reason:
        lines.append(f"ℹ️ {v.confidence_reason}")
    if v.cached:
        lines.append("(из кэша)")
    return "\n".join(lines)


def to_dict(v: Verdict) -> Dict[str, Any]:
    d = asdict(v)
    d["emoji"], d["label"] = label(v.verdict)
    return d
