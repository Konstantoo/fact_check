"""Минимальный верификатор утверждений: verify(claim) -> Verdict."""
from .service import Verdict, Source, FactCheck, verify  # noqa: F401
from .format import to_telegram_text, to_dict  # noqa: F401
