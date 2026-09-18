"""python -m verifier.cli "утверждение" """
import asyncio
import sys

from .format import to_telegram_text
from .service import verify


def main() -> None:
    claim = " ".join(sys.argv[1:]).strip()
    if not claim:
        print('Использование: python -m verifier.cli "утверждение или ссылка"')
        sys.exit(1)
    print(to_telegram_text(asyncio.run(verify(claim))))


if __name__ == "__main__":
    main()
