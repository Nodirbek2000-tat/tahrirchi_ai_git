from openpyxl import load_workbook

from data import config
from services.files.base import BaseProcessor, FileAnalysis, ceil_div


class XlsxProcessor(BaseProcessor):
    unit_name = "qator"

    def analyze(self, path: str) -> FileAnalysis:
        wb = load_workbook(path, read_only=True)
        rows = sum(ws.max_row or 0 for ws in wb.worksheets)
        wb.close()
        rows = max(1, rows)
        tokens = max(1, ceil_div(rows, config.ROWS_PER_TOKEN))
        return FileAnalysis(unit_count=rows, unit_name=self.unit_name, token_cost=tokens)

    def _extract(self, path: str):
        wb = load_workbook(path)
        cells = []
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str) and cell.value.strip():
                        cells.append(cell)
        segments = [cell.value for cell in cells]
        return (wb, cells), segments

    def _apply(self, context, corrected: list[str], out_path: str) -> None:
        wb, cells = context
        for cell, text in zip(cells, corrected):
            cell.value = text
        wb.save(out_path)
