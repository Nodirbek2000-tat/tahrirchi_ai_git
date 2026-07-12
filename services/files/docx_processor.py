"""DOCX: faqat harflarni (yoki tarjimani) o'zgartiradi, format/style/joylashuv saqlanadi.

Matn fayldagi BARCHA <w:t> tugunlaridan yig'iladi (body + kolontitullar, jadval,
ichma-ich jadval, matn qutilari, havolalar, SDT/TOC) — HECH BIR JOY TASHLANMAYDI.
"""

import zipfile
from xml.etree import ElementTree as ET

from docx import Document
from docx.document import Document as _Doc
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from data import config
from services.files.base import BaseProcessor, FileAnalysis, ceil_div

_APP_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"
_XML_SPACE = qn("xml:space")
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


def _text_containers(doc: _Doc) -> list:
    """Matn bo'lishi mumkin bo'lgan barcha ildiz elementlar: body + kolontitullar."""
    containers = [doc.element.body]
    for section in doc.sections:
        for hf in (section.header, section.footer):
            try:
                el = hf._element
                if el is not None:
                    containers.append(el)
            except Exception:
                pass
    return containers


def _collect_text_nodes(doc: _Doc) -> list:
    """Fayldagi BARCHA <w:t> matn tugunlari (bo'sh bo'lmagan)."""
    nodes = []
    seen = set()
    for container in _text_containers(doc):
        for t in container.iter(_W_T):
            if id(t) in seen:
                continue
            seen.add(id(t))
            if t.text and t.text.strip():
                nodes.append(t)
    return nodes


def _set_tables_fixed(doc: _Doc) -> None:
    """Jadval ustunlari kengligini qat'iy (fixed) qiladi — YONGA kengaymaydi."""
    for container in _text_containers(doc):
        for tbl in container.iter(qn("w:tbl")):
            tblPr = tbl.find(qn("w:tblPr"))
            if tblPr is None:
                tblPr = OxmlElement("w:tblPr")
                tbl.insert(0, tblPr)
            layout = tblPr.find(qn("w:tblLayout"))
            if layout is None:
                layout = OxmlElement("w:tblLayout")
                tblPr.append(layout)
            layout.set(qn("w:type"), "fixed")


class DocxProcessor(BaseProcessor):
    unit_name = "sahifa"

    def analyze(self, path: str) -> FileAnalysis:
        pages = _real_page_count(path)
        if pages is None:
            doc = Document(path)
            chars = sum(len(t.text) for t in _collect_text_nodes(doc))
            pages = max(1, ceil_div(chars, config.CHARS_PER_PAGE))
        return FileAnalysis(unit_count=pages, unit_name=self.unit_name, token_cost=pages)

    def _extract(self, path: str):
        doc = Document(path)
        nodes = _collect_text_nodes(doc)
        segments = [t.text for t in nodes]
        return (doc, nodes), segments

    def _apply(self, context, corrected: list[str], out_path: str) -> None:
        doc, nodes = context
        for node, text in zip(nodes, corrected):
            node.text = text
            if text != text.strip():
                node.set(_XML_SPACE, "preserve")
        _set_tables_fixed(doc)
        doc.save(out_path)
