"""PDF: matn o'qib olinadi, tuzatiladi va YANGI PDF (matn ko'rinishida) yaratiladi.

Eslatma: PDF ning asl joylashuvi/rasmlarini o'zgartirmasdan ichidagi harflarni
almashtirish texnik jihatdan imkonsizga yaqin. Shuning uchun natija — toza,
to'g'irlangan matnli yangi PDF.
"""

import os

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from services.files.base import BaseProcessor, FileAnalysis

_FONT_NAME = "UZFont"
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_font_registered = False


def _ensure_font() -> str:
    """ş, ç, ğ, ö harflarini qo'llaydigan shriftni ro'yxatdan o'tkazadi."""
    global _font_registered
    if _font_registered:
        return _FONT_NAME
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(_FONT_NAME, path))
            _font_registered = True
            return _FONT_NAME
    return "Helvetica"  # zaxira (kengaytirilgan harflarni to'liq qo'llamasligi mumkin)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class PdfProcessor(BaseProcessor):
    unit_name = "sahifa"

    def analyze(self, path: str) -> FileAnalysis:
        reader = PdfReader(path)
        pages = max(1, len(reader.pages))
        return FileAnalysis(unit_count=pages, unit_name=self.unit_name, token_cost=pages)

    def _extract(self, path: str):
        reader = PdfReader(path)
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        # Har sahifa uchun matn qatorlarini alohida segment qilamiz
        segments: list[str] = []
        page_line_counts: list[int] = []
        for text in pages:
            lines = text.split("\n")
            page_line_counts.append(len(lines))
            segments.extend(lines)
        return page_line_counts, segments

    def _apply(self, context, corrected: list[str], out_path: str) -> None:
        page_line_counts = context
        font = _ensure_font()

        styles = getSampleStyleSheet()
        style = styles["Normal"]
        style.fontName = font
        style.fontSize = 11
        style.leading = 16

        doc = SimpleDocTemplate(
            out_path,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        flow = []
        idx = 0
        for page_no, count in enumerate(page_line_counts):
            page_lines = corrected[idx : idx + count]
            idx += count
            for line in page_lines:
                if line.strip():
                    flow.append(Paragraph(_escape(line), style))
                else:
                    flow.append(Spacer(1, 8))
            if page_no < len(page_line_counts) - 1:
                flow.append(PageBreak())

        if not flow:
            flow.append(Paragraph("", style))
        doc.build(flow)
