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
        text = _read(path)
        tokens = max(1, ceil_div(len(text), config.CHARS_PER_PAGE))
        return FileAnalysis(unit_count=tokens, unit_name=self.unit_name, token_cost=tokens)

    def _extract(self, path: str):
        text = _read(path)
        lines = text.split("\n")
        return None, lines

    def _apply(self, context, corrected: list[str], out_path: str) -> None:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(corrected))
