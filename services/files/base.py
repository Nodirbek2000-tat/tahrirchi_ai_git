import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass

from services.corrector import TextCorrector


def ceil_div(a: int, b: int) -> int:
    return -(-a // b) if b else 0


@dataclass
class FileAnalysis:
    unit_count: int      # sahifa / slayd / qator soni
    unit_name: str       # "sahifa", "slayd", "qator"
    token_cost: int      # yechiladigan token


class BaseProcessor(ABC):
    """Barcha fayl turlari uchun umumiy interfeys.

    Og'ir (bloklovchi) ish `asyncio.to_thread` orqali alohida oqimda bajariladi,
    AI so'rovlari esa async holda — event loop bloklanmaydi.
    """

    unit_name: str = "sahifa"

    @abstractmethod
    def analyze(self, path: str) -> FileAnalysis:
        ...

    async def process(self, path: str, out_path: str, corrector: TextCorrector) -> None:
        context, segments = await asyncio.to_thread(self._extract, path)
        corrected = await corrector.correct_many(segments)
        await asyncio.to_thread(self._apply, context, corrected, out_path)

    @abstractmethod
    def _extract(self, path: str):
        """(context, segments) qaytaradi. context — matnni qayta yozish uchun holat."""
        ...

    @abstractmethod
    def _apply(self, context, corrected: list[str], out_path: str) -> None:
        ...
