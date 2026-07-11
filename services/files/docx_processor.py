import zipfile
from xml.etree import ElementTree as ET

from docx import Document
from docx.document import Document as _Doc
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from data import config
from services.files.base import BaseProcessor, FileAnalysis, ceil_div

# Word haqiqiy sahifa sonini shu yerda saqlaydi
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


def _iter_paragraphs(parent) -> list[Paragraph]:
    """Body, jadval kataklari va ichma-ich jadvallardagi barcha paragraflar."""
    paragraphs: list[Paragraph] = []
    if isinstance(parent, _Doc):
        container = parent.element.body
    else:
        container = parent._tc  # table cell

    for child in container.iterchildren():
        if child.tag.endswith("}p"):
            paragraphs.append(Paragraph(child, parent))
        elif child.tag.endswith("}tbl"):
            table = Table(child, parent)
            for row in table.rows:
                for cell in row.cells:
                    paragraphs.extend(_iter_paragraphs(cell))
    return paragraphs


def _all_paragraphs(doc: _Doc) -> list[Paragraph]:
    paragraphs = _iter_paragraphs(doc)
    # Kolontitullar (header/footer)
    for section in doc.sections:
        for hf in (section.header, section.footer):
            paragraphs.extend(hf.paragraphs)
    return paragraphs


def _collect_text_nodes(doc: _Doc) -> list:
    """Barcha <w:t> matn tugunlari (havola/hyperlink ichidagilar ham).

    Faqat matn tugunining STRING qismi o'zgaradi — page break, tab, rasm,
    uslub, joylashuv butunlay tegilmaydi.
    """
    nodes = []
    for para in _all_paragraphs(doc):
        for t in para._p.iter(_W_T):
            if t.text and t.text.strip():
                nodes.append(t)
    return nodes


def _set_tables_fixed(doc: _Doc) -> None:
    """Jadval ustunlari kengligini qat'iy (fixed) qiladi.

    Shunda tarjima/tahrir matni uzunroq bo'lsa ham jadval YONGA kengaymaydi —
    matn faqat pastga (bo'yiga) cho'ziladi, sahifadan chiqib ketmaydi.
    """
    containers = [doc.element.body]
    for section in doc.sections:
        for hf in (section.header, section.footer):
            try:
                containers.append(hf._element)
            except Exception:
                pass

    for container in containers:
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
        # 1-usul: Word saqlagan haqiqiy sahifa soni (eng aniq)
        pages = _real_page_count(path)
        if pages is None:
            # 2-usul (zaxira): belgilar soniga qarab taxminiy
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
            # Bosh/oxirgi bo'shliqlarni saqlab qolish
            if text != text.strip():
                node.set(_XML_SPACE, "preserve")
        # Jadvallar yonga kengayib ketmasligi uchun
        _set_tables_fixed(doc)
        doc.save(out_path)
