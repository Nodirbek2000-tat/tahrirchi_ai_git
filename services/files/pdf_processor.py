"""PDF: PDF -> Word -> tahrir (harf/tarjima) -> PDF.

1) pdf2docx bilan PDF -> DOCX (matn, rasm, jadval, joylashuv saqlanadi)
2) DocxProcessor bilan tahrir (barcha <w:t> — hech joy tashlanmaydi, style saqlanadi)
3) LibreOffice bilan DOCX -> PDF (asl ko'rinish render qilinadi)

Eslatma: skaner qilingan (faqat rasmli) PDF'da tahrirlanadigan matn bo'lmaydi —
rasm o'z holicha qoladi.
"""

import asyncio
import os
import uuid

from pypdf import PdfReader

from services.corrector import TextCorrector
from services.files.base import BaseProcessor, FileAnalysis
from services.files.convert import docx_to_pdf, pdf_to_docx
from services.files.docx_processor import DocxProcessor


class PdfProcessor(BaseProcessor):
    unit_name = "sahifa"

    def analyze(self, path: str) -> FileAnalysis:
        pages = max(1, len(PdfReader(path).pages))
        return FileAnalysis(unit_count=pages, unit_name=self.unit_name, token_cost=pages)

    # Quvur to'liq qayta yozilgani uchun _extract/_apply ishlatilmaydi
    def _extract(self, path: str):
        raise NotImplementedError

    def _apply(self, context, corrected: list[str], out_path: str) -> None:
        raise NotImplementedError

    async def process(self, path: str, out_path: str, corrector: TextCorrector) -> None:
        workdir = os.path.dirname(out_path) or "."
        uid = uuid.uuid4().hex[:8]
        conv_docx = os.path.join(workdir, f"_conv_{uid}.docx")
        edited_docx = os.path.join(workdir, f"_edited_{uid}.docx")

        # 1) PDF -> DOCX
        await asyncio.to_thread(pdf_to_docx, path, conv_docx)
        # 2) DOCX tahrir (harf yoki tarjima) — mavjud ishonchli docx quvuri
        await DocxProcessor().process(conv_docx, edited_docx, corrector)
        # 3) DOCX -> PDF
        await asyncio.to_thread(docx_to_pdf, edited_docx, out_path)
