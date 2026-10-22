"""DOCX hajmi (sahifa soni)."""

import zipfile
from xml.etree import ElementTree as ET

from docx import Document
from docx.oxml.ns import qn

from data import config
from services.files.base import BaseProcessor, FileAnalysis, ceil_div

_APP_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"
_W_T = qn("w:t")


def _real_page_count(path: str) -> int | None:
    """Word saqlagan haqiqiy sahifa soni (docProps/app.xml -> <Pages>)."""
    try:
        with zipfile.ZipFile(path) as z:
            data = z.read("docProps/app.xml")
        root = ET.fromstring(data)
        el = root.find(_APP_NS + "Pages")
        if el is not None and el.text and el.text.strip().isdigit():
            n = int(el.text.strip())
            if n > 0:
                return n
    except Exception:
        pass
    return None


def _text_length(path: str) -> int:
    """Hujjatdagi (body + kolontitullar) barcha matn uzunligi."""
    doc = Document(path)
    containers = [doc.element.body]
    for section in doc.sections:
        for hf in (section.header, section.footer):
            try:
                containers.append(hf._element)
            except Exception:
                pass
    return sum(len(t.text or "") for c in containers if c is not None for t in c.iter(_W_T))


class DocxProcessor(BaseProcessor):
    unit_name = "sahifa"

    def analyze(self, path: str) -> FileAnalysis:
        pages = _real_page_count(path)
        if pages is None:
            pages = max(1, ceil_div(_text_length(path), config.CHARS_PER_PAGE))
        return FileAnalysis(unit_count=pages, unit_name=self.unit_name, pages=pages)
