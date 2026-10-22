"""TXT hajmi (belgilar bo'yicha sahifa)."""

from data import config
from services.files.base import BaseProcessor, FileAnalysis, ceil_div


def _read(path: str) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


class TxtProcessor(BaseProcessor):
    unit_name = "sahifa"

    def analyze(self, path: str) -> FileAnalysis:
        pages = max(1, ceil_div(len(_read(path)), config.CHARS_PER_PAGE))
        return FileAnalysis(unit_count=pages, unit_name=self.unit_name, pages=pages)
