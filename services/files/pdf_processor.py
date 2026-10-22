"""PDF hajmi (sahifa soni). Tahrir PDF'ning o'zida — services/files/pdf_inplace.py."""

from pypdf import PdfReader

from services.files.base import BaseProcessor, FileAnalysis


class PdfProcessor(BaseProcessor):
    unit_name = "sahifa"

    def analyze(self, path: str) -> FileAnalysis:
        pages = max(1, len(PdfReader(path).pages))
        return FileAnalysis(unit_count=pages, unit_name=self.unit_name, pages=pages)
