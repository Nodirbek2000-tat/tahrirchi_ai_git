from abc import ABC, abstractmethod
from dataclasses import dataclass


def ceil_div(a: int, b: int) -> int:
    return -(-a // b) if b else 0


@dataclass
class FileAnalysis:
    unit_count: int      # sahifa / slayd / qator soni
    unit_name: str       # "sahifa", "slayd", "qator"
    pages: int           # hajm sahifada (maksimal hajm cheklovi uchun)


class BaseProcessor(ABC):
    """Fayl hajmini aniqlaydi. Tahrirning o'zi — services/files/translit_engine.py."""

    unit_name: str = "sahifa"

    @abstractmethod
    def analyze(self, path: str) -> FileAnalysis:
        ...
