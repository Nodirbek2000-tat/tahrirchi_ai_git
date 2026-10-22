"""PPTX hajmi (slaydlar soni)."""

from pptx import Presentation

from services.files.base import BaseProcessor, FileAnalysis


class PptxProcessor(BaseProcessor):
    unit_name = "slayd"

    def analyze(self, path: str) -> FileAnalysis:
        prs = Presentation(path)
        slides = len(prs.slides._sldIdLst)
        return FileAnalysis(unit_count=slides, unit_name=self.unit_name, pages=max(1, slides))
