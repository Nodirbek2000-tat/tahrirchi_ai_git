"""Fayllarni harf/yozuv bo'yicha to'liq o'girish — AI'siz, XML darajasida.

Ishlatiladi:
  - yangi alifbo: sh/ch/gʻ/oʻ -> ş/ç/ğ/ö
  - kirill <-> lotin (services/converters.py dagi qoidalar)

Word / Excel / PowerPoint fayli (zip) ichidagi matnli XML qismlar to'g'ridan-to'g'ri
tahrirlanadi: faqat matn harflari o'zgaradi — style, shrift, rang, rasm, jadval va
joylashuv bayt-bayt o'zgarishsiz qoladi (o'zgarmagan qismlar asl holida nusxalanadi).

Muhim: Word, Excel va PowerPoint bitta so'zni ko'pincha bir nechta bo'lakka ("run")
bo'lib saqlaydi — masalan "s" bir bo'lakda, "hahar" boshqasida yoki "o" va "ʻ" alohida.
Shuning uchun harflar paragraf (Excel'da katak) darajasida birlashtirib qidiriladi,
yangi matn esa asl bo'lagiga qaytarib yoziladi — hech bir joy qolib ketmaydi.

Qamrov:
  Word       — asosiy matn, jadval, kolontitul, izoh, sahifa osti izohlari, matn qutilari,
               havolalar, diagramma va SmartArt matni
  PowerPoint — slaydlar, izohlar (notes), slayd master va layout'lar, jadval, guruh,
               diagramma, SmartArt
  Excel      — kataklar (shared/inline/rich text), izohlar, shakllar, diagrammalar;
               jadval ustun nomlari va formulalardagi havolalar sarlavhaga moslab o'giriladi,
               formulalar ichidagi matnli qiymatlar, filtr va ro'yxat qiymatlari ham o'giriladi
  Ichki fayllar — diagramma ichidagi Excel ma'lumotlari (embeddings) ham o'giriladi

Bosqichlar:
  1) skan       — nechta o'zgartiriladigan joy borligi aniqlanadi
  2) o'girish   — har bir topilgan joy almashtiriladi
  3) qayta skan — qolgan bo'lsa yana o'giriladi (maksimal 3 marta)
  4) yozish     — faqat o'zgargan qismlar qayta yoziladi
  5) yakuniy tekshiruv — SAQLANGAN fayl qayta ochilib skan qilinadi
"""

import io
import logging
import os
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field

from lxml import etree

from services.converters import NEW_ALPHABET, Converter
from services.files.pdf_inplace import scan_pdf, transliterate_pdf
from services.transliteration import APOSTROPHES

logger = logging.getLogger(__name__)

_MAX_ROUNDS = 3
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_PARSER = etree.XMLParser(
    resolve_entities=False, no_network=True, huge_tree=True, remove_blank_text=False
)
_EMBED_RE = re.compile(r"^(word|ppt|xl)/embeddings/[^/]+\.(xlsx|docx|pptx)$", re.IGNORECASE)

# Transitional va Strict OOXML nomlar fazolari
_W = ("http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "http://purl.oclc.org/ooxml/wordprocessingml/main")
_A = ("http://schemas.openxmlformats.org/drawingml/2006/main",
      "http://purl.oclc.org/ooxml/drawingml/main")
_S = ("http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "http://purl.oclc.org/ooxml/spreadsheetml/main")
_C = ("http://schemas.openxmlformats.org/drawingml/2006/chart",
      "http://purl.oclc.org/ooxml/drawingml/chart")
_P = ("http://schemas.openxmlformats.org/presentationml/2006/main",
      "http://purl.oclc.org/ooxml/presentationml/main")
_XM = ("http://schemas.microsoft.com/office/excel/2006/main",)
_TC = ("http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments",)


def _q(namespaces, *names) -> frozenset:
    return frozenset(f"{{{ns}}}{name}" for ns in namespaces for name in names)


# ======================================================================= Matn tugunlari
@dataclass(frozen=True)
class _Spec:
    text: frozenset                     # matn tugunlari
    groups: frozenset                   # birlashtirish birligi; bo'sh => har tugun alohida
    breaks: frozenset = frozenset()     # so'zlarni ajratuvchi elementlar (tab, br ...)
    syms: frozenset = frozenset()       # w:sym — belgi sifatida qo'yilgan tutuq
    exclude: frozenset = frozenset()    # shu ajdod ichidagi matn olinmaydi
    preserve_space: bool = False        # xml:space="preserve" kerakmi
    flow: bool = False                  # paragraflar o'qish tartibida (qo'shni kontekst bor)


_WORD = _Spec(
    text=_q(_W, "t"),
    groups=_q(_W, "p"),
    breaks=_q(_W, "tab", "br", "cr", "ptab", "noBreakHyphen", "drawing", "pict",
              "object", "fldChar", "footnoteReference", "endnoteReference"),
    syms=_q(_W, "sym"),
    preserve_space=True,
    flow=True,
)
_DRAWING = _Spec(text=_q(_A, "t"), groups=_q(_A, "p"), breaks=_q(_A, "br"), flow=True)
_SHEET = _Spec(
    text=_q(_S, "t"),
    groups=_q(_S, "si", "is", "text"),   # shared string / inline string / izoh
    exclude=_q(_S, "rPh"),               # fonetik yozuvlar
    preserve_space=True,
)
_CHART_CACHE = _Spec(text=_q(_C, "v"), groups=frozenset())
_PPT_OLD_COMMENT = _Spec(text=_q(_P, "text"), groups=frozenset())
_XL_THREADED = _Spec(text=_q(_TC, "text"), groups=frozenset())

# Excel uchun qo'shimcha ishlov turlari
_XL_SHEET = "xl_sheet"   # formulalar, formula natijasi (keshi), filtr qiymatlari
_XL_TABLE = "xl_table"   # jadval ustun nomlari, jadval formulalari
_XL_BOOK = "xl_book"     # nomlangan diapazon formulalari

_WORDS = (_WORD, _DRAWING)

# Content-Type bo'yicha: (qo'shimcha nomi, matn qoidalari, qo'shimcha ishlovlar)
_CT_RULES = (
    ("wordprocessingml.document.main+xml", _WORDS, ()),
    ("wordprocessingml.template.main+xml", _WORDS, ()),
    ("ms-word.document.macroEnabled.main+xml", _WORDS, ()),
    ("wordprocessingml.header+xml", _WORDS, ()),
    ("wordprocessingml.footer+xml", _WORDS, ()),
    ("wordprocessingml.footnotes+xml", _WORDS, ()),
    ("wordprocessingml.endnotes+xml", _WORDS, ()),
    ("wordprocessingml.comments+xml", _WORDS, ()),
    ("spreadsheetml.sharedStrings+xml", (_SHEET,), ()),
    ("spreadsheetml.worksheet+xml", (_SHEET,), (_XL_SHEET,)),
    ("spreadsheetml.comments+xml", (_SHEET,), ()),
    ("spreadsheetml.table+xml", (), (_XL_TABLE,)),
    ("spreadsheetml.sheet.main+xml", (), (_XL_BOOK,)),
    ("ms-excel.sheet.macroEnabled.main+xml", (), (_XL_BOOK,)),
    ("ms-excel.threadedcomments+xml", (_XL_THREADED,), ()),
    ("presentationml.slide+xml", (_DRAWING,), ()),
    ("presentationml.notesSlide+xml", (_DRAWING,), ()),
    ("presentationml.slideMaster+xml", (_DRAWING,), ()),
    ("presentationml.slideLayout+xml", (_DRAWING,), ()),
    ("presentationml.notesMaster+xml", (_DRAWING,), ()),
    ("presentationml.handoutMaster+xml", (_DRAWING,), ()),
    ("presentationml.comments+xml", (_PPT_OLD_COMMENT,), ()),
    ("ms-powerpoint.comments+xml", (_DRAWING,), ()),
    ("drawingml.chart+xml", (_DRAWING, _CHART_CACHE), ()),
    ("drawingml.diagramData+xml", (_DRAWING,), ()),
    ("drawingml.diagramDrawing+xml", (_DRAWING,), ()),
    ("officedocument.drawing+xml", (_DRAWING,), ()),
)

# Content-Type topilmasa — fayl nomi bo'yicha (zaxira)
_NAME_RULES = (
    (re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"),
     _WORDS, ()),
    (re.compile(r"^xl/(sharedstrings|comments\d*)\.xml$"), (_SHEET,), ()),
    (re.compile(r"^xl/worksheets/sheet\d+\.xml$"), (_SHEET,), (_XL_SHEET,)),
    (re.compile(r"^xl/tables/table\d+\.xml$"), (), (_XL_TABLE,)),
    (re.compile(r"^xl/workbook\.xml$"), (), (_XL_BOOK,)),
    (re.compile(r"^ppt/(slides/slide|notesslides/notesslide|slidemasters/slidemaster|"
                r"slidelayouts/slidelayout)\d+\.xml$"), (_DRAWING,), ()),
    (re.compile(r"^(word|ppt|xl)/charts/chart\d+\.xml$"), (_DRAWING, _CHART_CACHE), ()),
    (re.compile(r"^(word|ppt|xl)/diagrams/(data|drawing)\d+\.xml$"), (_DRAWING,), ()),
    (re.compile(r"^xl/drawings/drawing\d+\.xml$"), (_DRAWING,), ()),
)


@dataclass
class TranslitReport:
    found: Counter = field(default_factory=Counter)  # boshida topilganlar (turi bo'yicha)
    converted: int = 0                               # o'zgartirilganlar
    remaining: int = 0                               # yakuniy tekshiruvda qolganlar
    passes: int = 0                                  # nechta tahlil bosqichi o'tdi

    @property
    def total_found(self) -> int:
        return sum(self.found.values())


@dataclass
class _Part:
    root: object
    specs: tuple
    extras: tuple
    data: bytes


# ======================================================================= XML yordamchilar
def _content_types(zin: zipfile.ZipFile) -> dict:
    try:
        root = etree.fromstring(zin.read("[Content_Types].xml"), _PARSER)
    except (KeyError, etree.XMLSyntaxError):
        return {}
    result = {}
    for el in root:
        if isinstance(el.tag, str) and el.tag.endswith("}Override"):
            name = (el.get("PartName") or "").lstrip("/").lower()
            result[name] = el.get("ContentType") or ""
    return result


def _rules_for(name: str, ctypes: dict) -> tuple[tuple, tuple]:
    lname = name.lower()
    ct = ctypes.get(lname)
    if ct:
        for suffix, specs, extras in _CT_RULES:
            if ct.endswith(suffix):
                return specs, extras
        return (), ()
    for rx, specs, extras in _NAME_RULES:
        if rx.match(lname):
            return specs, extras
    return (), ()


def _sym_char(el) -> str | None:
    """w:sym tutuq belgisi bo'lsa, o'sha belgini qaytaradi."""
    for key, value in el.attrib.items():
        if key.endswith("}char"):
            try:
                ch = chr(int(value, 16))
            except ValueError:
                return None
            return ch if ch in APOSTROPHES else None
    return None


def _build_groups(root, spec: _Spec) -> dict:
    """Har bir guruh (paragraf) uchun hujjat tartibidagi bo'laklar ro'yxati.

    Bo'lak: ("t", element) | ("sym", element, belgi) | None (so'z chegarasi).
    """
    groups: dict = {}
    for el in root.iter(*(spec.text | spec.breaks | spec.syms)):
        grp = el
        if spec.groups:
            grp = None
            parent = el.getparent()
            excluded = False
            while parent is not None:
                ptag = parent.tag
                if ptag in spec.exclude:
                    excluded = True
                    break
                if ptag in spec.groups:
                    grp = parent
                    break
                parent = parent.getparent()
            if excluded:
                continue
            if grp is None:
                grp = el

        pieces = groups.get(grp)
        if pieces is None:
            pieces = groups[grp] = []

        tag = el.tag
        if tag in spec.text:
            pieces.append(("t", el))
        elif tag in spec.syms:
            ch = _sym_char(el)
            pieces.append(("sym", el, ch) if ch else None)
        else:
            pieces.append(None)
    return groups


def _segments(pieces):
    seg = []
    for piece in pieces:
        if piece is None:
            if seg:
                yield seg
                seg = []
        else:
            seg.append(piece)
    if seg:
        yield seg


def _piece_text(piece) -> str:
    return (piece[1].text or "") if piece[0] == "t" else piece[2]


def _replace_sym(el, new: str) -> None:
    """w:sym ni o'chiradi yoki (yangi matn bo'lsa) shu runda w:t bilan almashtiradi."""
    parent = el.getparent()
    if parent is None:
        return
    if not new:
        parent.remove(el)
        return
    ns = el.tag[1:].split("}", 1)[0]
    text_el = etree.Element(f"{{{ns}}}t")
    text_el.text = new
    if new != new.strip():
        text_el.set(_XML_SPACE, "preserve")
    parent.replace(el, text_el)


def _spec_segments(root, spec: _Spec, conv: Converter):
    """(bo'laklar, birlashgan matn, kontekst) — hujjat tartibida.

    Kataklar (Excel) bir-biriga bog'liq emas va jadval ustun nomlari bilan bir xil
    o'girilishi shart — shuning uchun ularga qo'shni kontekst berilmaydi.
    """
    segs, firsts = [], []
    for pieces in _build_groups(root, spec).values():
        for k, seg in enumerate(_segments(pieces)):
            segs.append(seg)
            firsts.append(k == 0)
    texts = ["".join(_piece_text(p) for p in seg) for seg in segs]
    ctxs = conv.contexts(texts, firsts) if spec.flow else [None] * len(texts)
    return zip(segs, texts, ctxs)


def _spec_conv(spec: _Spec, conv: Converter) -> Converter:
    return conv if spec.flow else conv.for_cells()


def _scan_text(root, specs, conv: Converter, counter: Counter) -> None:
    for spec in specs:
        c = _spec_conv(spec, conv)
        for _, joined, ctx in _spec_segments(root, spec, c):
            if joined:
                counter.update(c.count(joined, ctx))


def _apply_text(root, specs, conv: Converter) -> int:
    changed = 0
    for spec in specs:
        c = _spec_conv(spec, conv)
        for seg, joined, ctx in _spec_segments(root, spec, c):
            if not joined:
                continue
            edits = c.edits(joined, ctx)
            if not edits:
                continue
            texts = [_piece_text(p) for p in seg]

            # Birlashtirilgan matndagi pozitsiya -> (bo'lak, ichki o'rni)
            owner = []
            for i, text in enumerate(texts):
                owner.extend((i, j) for j in range(len(text)))
            chars: list[list] = [list(text) for text in texts]
            for start, end, replacement, _ in edits:
                i, j = owner[start]
                chars[i][j] = replacement        # yangi matn birinchi belgi o'rnida
                for pos in range(start + 1, end):
                    i, j = owner[pos]
                    chars[i][j] = None           # qolgan belgilar o'chiriladi
            changed += len(edits)

            for piece, piece_chars, old in zip(seg, chars, texts):
                new = "".join(c for c in piece_chars if c is not None)
                if new == old:
                    continue
                if piece[0] == "t":
                    piece[1].text = new
                    if spec.preserve_space and new != new.strip():
                        piece[1].set(_XML_SPACE, "preserve")
                else:
                    _replace_sym(piece[1], new)
    return changed


# ======================================================================= Excel qo'shimchalari
_F_SHEET = _q(_S, "f", "formula", "formula1", "formula2") | _q(_XM, "f")
_F_TABLE = _q(_S, "calculatedColumnFormula", "totalsRowFormula")
_F_BOOK = _q(_S, "definedName")
_FILTER_VAL = _q(_S, "filter", "customFilter")
_CELL = _q(_S, "c")
_VALUE = _q(_S, "v")
_TABLE_COL = _q(_S, "tableColumn")
_TABLE = _q(_S, "table")
_SHEET_NAME = _q(_S, "sheet")

_STR_LIT_RE = re.compile(r'"(?:[^"]|"")*"')
# Matnli qiymat havola bo'lsa (INDIRECT("Varaq!A1"), fayl yo'li) — tegilmaydi
_REF_LITERAL_RE = re.compile(r"![$]?[A-Za-z]{1,3}[$]?\d|\\")
# Sana/vaqt format kodi (TEXT(A1;"dd.mm.yyyy"), "ДД.ММ.ГГГГ") — tegilmaydi
_FORMAT_CODE_RE = re.compile(
    r"(?=.*(?:dd|mm|yy|hh|ss|дд|мм|гг|чч|сс))[dmyhsдмгчс/.:,\s\-]+", re.IGNORECASE
)
# Katak manzili ("A1", "$B$12") — tegilmaydi
_CELL_REF_RE = re.compile(r"\$?[A-Za-z]{1,3}\$?\d{1,7}")


@dataclass
class _XlContext:
    col_refs: list           # [(regex, yangi_nom)] — jadval ustuni nomlari
    protected: frozenset     # varaq / nomlangan diapazon / jadval nomlari (kichik harfda)


def _esc_struct(name: str) -> str:
    """Excel strukturaviy havolasidagi maxsus belgilarni ekranlash: [ ] # '"""
    return re.sub(r"([\[\]#'])", r"'\1", name)


def _xl_context(parts: dict, conv: Converter) -> _XlContext:
    col_refs = []
    protected = set()
    for part in parts.values():
        if _XL_TABLE in part.extras:
            for tbl in part.root.iter(*_TABLE):
                for attr in ("name", "displayName"):
                    if tbl.get(attr):
                        protected.add(tbl.get(attr).lower())
            for col in part.root.iter(*_TABLE_COL):
                old = col.get("name")
                if not old:
                    continue
                new = conv.convert(old)
                if new != old:
                    # [Nom], [@Nom] va qavssiz ",Nom]" ([[#This Row],Nom]) shakllari
                    rx = re.compile(
                        r"(\[@?|,\s*)" + re.escape(_esc_struct(old)) + r"(\])", re.IGNORECASE
                    )
                    col_refs.append((rx, _esc_struct(new)))
        if _XL_BOOK in part.extras:
            for el in part.root.iter(*_SHEET_NAME):
                if el.get("name"):
                    protected.add(el.get("name").lower())
            for el in part.root.iter(*_F_BOOK):
                if el.get("name"):
                    protected.add(el.get("name").lower())
    return _XlContext(col_refs, frozenset(protected))


def _literal_ok(inner: str, ctx: _XlContext) -> bool:
    return (
        bool(inner)
        and inner.lower() not in ctx.protected
        and not _REF_LITERAL_RE.search(inner)
        and not _FORMAT_CODE_RE.fullmatch(inner)
        and not _CELL_REF_RE.fullmatch(inner)
    )


def _formula_count(text, ctx: _XlContext, conv: Converter, counter: Counter) -> None:
    if not text or '"' not in text:
        return
    for m in _STR_LIT_RE.finditer(text):
        inner = m.group(0)[1:-1]
        if _literal_ok(inner, ctx):
            counter.update(conv.count(inner))


def _formula_convert(text, ctx: _XlContext, conv: Converter) -> tuple:
    if not text:
        return text, 0
    changed = 0

    def repl(m):
        nonlocal changed
        inner = m.group(0)[1:-1]
        if not _literal_ok(inner, ctx):
            return m.group(0)
        n = sum(conv.count(inner).values())
        if not n:
            return m.group(0)
        changed += n
        return '"' + conv.convert(inner) + '"'

    new = _STR_LIT_RE.sub(repl, text) if '"' in text else text
    for rx, new_name in ctx.col_refs:   # jadval ustunlariga havolalar sarlavhaga moslanadi
        new = rx.sub(lambda m, nn=new_name: m.group(1) + nn + m.group(2), new)
    return new, changed


def _attr_count(el, attr: str, conv: Converter, counter: Counter) -> None:
    value = el.get(attr)
    if value:
        counter.update(conv.count(value))


def _attr_convert(el, attr: str, conv: Converter) -> int:
    value = el.get(attr)
    if not value:
        return 0
    n = sum(conv.count(value).values())
    if n:
        el.set(attr, conv.convert(value))
    return n


def _str_results(root):
    """Formula natijasi matn bo'lgan kataklarning keshdagi qiymati (<c t="str"><v>)."""
    for cell in root.iter(*_CELL):
        if cell.get("t") == "str":
            for child in cell:
                if child.tag in _VALUE:
                    yield child


def _extras_count(part: _Part, ctx: _XlContext, conv: Converter, counter: Counter) -> None:
    root = part.root
    for kind in part.extras:
        if kind == _XL_SHEET:
            for el in root.iter(*_F_SHEET):
                _formula_count(el.text, ctx, conv, counter)
            for v in _str_results(root):
                counter.update(conv.count(v.text or ""))
            for el in root.iter(*_FILTER_VAL):
                _attr_count(el, "val", conv, counter)
        elif kind == _XL_TABLE:
            for el in root.iter(*_TABLE_COL):
                _attr_count(el, "name", conv, counter)
                _attr_count(el, "totalsRowLabel", conv, counter)
            for el in root.iter(*_F_TABLE):
                _formula_count(el.text, ctx, conv, counter)
            for el in root.iter(*_FILTER_VAL):
                _attr_count(el, "val", conv, counter)
        elif kind == _XL_BOOK:
            for el in root.iter(*_F_BOOK):
                _formula_count(el.text, ctx, conv, counter)


def _extras_apply(part: _Part, ctx: _XlContext, conv: Converter) -> int:
    root = part.root
    changed = 0

    def formula_elements(tags):
        nonlocal changed
        for el in root.iter(*tags):
            new, n = _formula_convert(el.text, ctx, conv)
            if new != el.text:
                el.text = new
            changed += n

    for kind in part.extras:
        if kind == _XL_SHEET:
            formula_elements(_F_SHEET)
            for v in _str_results(root):
                n = sum(conv.count(v.text or "").values())
                if n:
                    v.text = conv.convert(v.text)
                    changed += n
            for el in root.iter(*_FILTER_VAL):
                changed += _attr_convert(el, "val", conv)
        elif kind == _XL_TABLE:
            for el in root.iter(*_TABLE_COL):
                changed += _attr_convert(el, "name", conv)
                changed += _attr_convert(el, "totalsRowLabel", conv)
            formula_elements(_F_TABLE)
            for el in root.iter(*_FILTER_VAL):
                changed += _attr_convert(el, "val", conv)
        elif kind == _XL_BOOK:
            formula_elements(_F_BOOK)
    return changed


# ======================================================================= Fayl darajasi
def _serialize(root, original: bytes) -> bytes:
    standalone = True if b"standalone" in original[:200] else None
    return etree.tostring(
        root.getroottree(), xml_declaration=True, encoding="UTF-8", standalone=standalone
    )


def _load_parts(zin: zipfile.ZipFile) -> dict:
    ctypes = _content_types(zin)
    parts = {}
    for info in zin.infolist():
        specs, extras = _rules_for(info.filename, ctypes)
        if not specs and not extras:
            continue
        data = zin.read(info.filename)
        try:
            root = etree.fromstring(data, _PARSER)
        except etree.XMLSyntaxError as exc:
            logger.warning("XML o'qilmadi (%s): %s", info.filename, exc)
            continue
        parts[info.filename] = _Part(root, specs, extras, data)
    return parts


def _scan_parts(parts: dict, conv: Converter) -> Counter:
    counter: Counter = Counter()
    cell_conv = conv.for_cells()
    ctx = _xl_context(parts, cell_conv)
    for part in parts.values():
        _scan_text(part.root, part.specs, conv, counter)
        if part.extras:
            _extras_count(part, ctx, cell_conv, counter)
    return counter


def _scan_zip(zin: zipfile.ZipFile, conv: Converter, depth: int = 0) -> Counter:
    counter = _scan_parts(_load_parts(zin), conv)
    if depth == 0:
        for name in zin.namelist():
            if _EMBED_RE.match(name):
                try:
                    with zipfile.ZipFile(io.BytesIO(zin.read(name))) as sub:
                        counter.update(_scan_zip(sub, conv, depth + 1))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Ichki fayl skan qilinmadi (%s): %s", name, exc)
    return counter


def _copy_info(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    new = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    new.compress_type = info.compress_type
    new.external_attr = info.external_attr
    new.create_system = info.create_system
    return new


def _convert_zip(zin: zipfile.ZipFile, zout: zipfile.ZipFile, report: TranslitReport,
                 conv: Converter, depth: int = 0) -> int:
    """Zip ichidagi barcha qismlarni o'giradi. Bajarilgan o'girish raundlari sonini qaytaradi."""
    parts = _load_parts(zin)

    # 1) Skan
    found = _scan_parts(parts, conv)
    report.found.update(found)

    # 2-3) O'girish + xotirada qayta skan (qolsa yana o'giriladi)
    changed: set = set()
    remaining = sum(found.values())
    rounds = 0
    cell_conv = conv.for_cells()
    while remaining and rounds < _MAX_ROUNDS:
        rounds += 1
        ctx = _xl_context(parts, cell_conv)   # jadval nomlari o'girilishidan OLDIN olinadi
        for name, part in parts.items():
            n = _apply_text(part.root, part.specs, conv)
            if part.extras:
                n += _extras_apply(part, ctx, cell_conv)
            if n:
                changed.add(name)
                report.converted += n
        remaining = sum(_scan_parts(parts, conv).values())

    # 4) Yozish — o'zgarmagan qismlar asl baytlari bilan nusxalanadi
    for info in zin.infolist():
        name = info.filename
        if name in changed:
            data = _serialize(parts[name].root, parts[name].data)
        elif depth == 0 and _EMBED_RE.match(name):
            data = _convert_embedded(zin.read(name), report, conv)
        else:
            data = zin.read(name)
        zout.writestr(_copy_info(info), data)
    return rounds


def _convert_embedded(data: bytes, report: TranslitReport, conv: Converter) -> bytes:
    """Ichki Word/Excel/PowerPoint fayl (masalan diagramma ma'lumotlari)."""
    try:
        sub_report = TranslitReport()
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as sub_in, zipfile.ZipFile(buf, "w") as sub_out:
            _convert_zip(sub_in, sub_out, sub_report, conv, depth=1)
        if not sub_report.converted:
            return data
        report.found.update(sub_report.found)
        report.converted += sub_report.converted
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ichki fayl o'girilmadi, asl holida qoldi: %s", exc)
        return data


def _leftovers(path: str, conv: Converter, limit: int = 10) -> list[str]:
    """Yakuniy tekshiruvda qolgan matn joylari (log uchun)."""
    found = []
    with zipfile.ZipFile(path) as zin:
        for name, part in _load_parts(zin).items():
            for spec in part.specs:
                c = _spec_conv(spec, conv)
                for _, joined, ctx in _spec_segments(part.root, spec, c):
                    for start, _, _, _ in c.edits(joined, ctx):
                        found.append(f"{name}: …{joined[max(0, start - 15):start + 15]}…")
                        if len(found) >= limit:
                            return found
    return found


# ======================================================================= Ommaviy API
def scan_file(path: str, conv: Converter = NEW_ALPHABET) -> Counter | None:
    """Fayldagi o'zgartiriladigan joylar soni (turi bo'yicha)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return _txt_count(_read_txt(path), conv)
    if ext in (".docx", ".xlsx", ".pptx"):
        with zipfile.ZipFile(path) as zin:
            return _scan_zip(zin, conv)
    if ext == ".pdf":
        return scan_pdf(path, conv)
    return None


def flow_texts(path: str, conv: Converter) -> list[tuple[str, object]]:
    """Oddiy matn paragraflari (Word, PowerPoint, TXT) kontekstlari bilan — masalan,
    AI'ga yuboriladigan gaplarni tanlash uchun. Excel kataklari va PDF kirmaydi."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        lines = _read_txt(path).split("\n")
        return list(zip(lines, conv.contexts(lines)))
    if ext not in (".docx", ".pptx"):
        return []
    out = []
    with zipfile.ZipFile(path) as zin:
        for part in _load_parts(zin).values():
            for spec in part.specs:
                if spec.flow:
                    out.extend((t, c) for _, t, c in _spec_segments(part.root, spec, conv) if t)
    return out


def _transliterate_ooxml(in_path: str, out_path: str, conv: Converter) -> TranslitReport:
    report = TranslitReport()
    with zipfile.ZipFile(in_path) as zin, zipfile.ZipFile(out_path, "w") as zout:
        rounds = _convert_zip(zin, zout, report, conv)

    # 5) Yakuniy tekshiruv — saqlangan fayl qayta ochiladi
    report.remaining = sum((scan_file(out_path, conv) or Counter()).values())
    report.passes = 1 + rounds + 1   # skan + o'girish raundlari + yakuniy tekshiruv
    if report.remaining:
        logger.warning(
            "Yakuniy tekshiruvda %s ta joy qoldi: %s",
            report.remaining, _leftovers(out_path, conv),
        )
    return report


def _read_txt(path: str) -> str:
    """Matn faylini qator oxirlari (\\r\\n / \\n) o'zgarmagan holda o'qish."""
    with open(path, "rb") as f:
        data = f.read()
    for encoding in ("utf-8", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _txt_count(text: str, conv: Converter) -> Counter:
    """Matn fayli qatorma-qator (har qator — paragraf, tili alohida aniqlanadi)."""
    lines = text.split("\n")
    counter: Counter = Counter()
    for line, ctx in zip(lines, conv.contexts(lines)):
        if line:
            counter.update(conv.count(line, ctx))
    return counter


def _txt_convert(text: str, conv: Converter) -> str:
    lines = text.split("\n")
    return "\n".join(conv.convert(line, ctx) for line, ctx in zip(lines, conv.contexts(lines)))


def _transliterate_txt(in_path: str, out_path: str, conv: Converter) -> TranslitReport:
    report = TranslitReport()
    text = _read_txt(in_path)
    report.found = _txt_count(text, conv)

    remaining = report.total_found
    rounds = 0
    while remaining and rounds < _MAX_ROUNDS:
        rounds += 1
        before = remaining
        text = _txt_convert(text, conv)
        remaining = sum(_txt_count(text, conv).values())
        report.converted += before - remaining

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    report.remaining = sum(_txt_count(_read_txt(out_path), conv).values())
    report.passes = 1 + rounds + 1
    return report


def transliterate_file(
    in_path: str, out_path: str, conv: Converter = NEW_ALPHABET
) -> TranslitReport:
    """Faylni berilgan qoida bo'yicha o'giradi (bloklovchi — asyncio.to_thread bilan)."""
    ext = os.path.splitext(in_path)[1].lower()
    if ext == ".txt":
        return _transliterate_txt(in_path, out_path, conv)
    if ext in (".docx", ".xlsx", ".pptx"):
        return _transliterate_ooxml(in_path, out_path, conv)
    if ext == ".pdf":
        # PDF Word'ga o'tkazilmaydi — asl dizaynida, faqat kerakli so'zlar qayta yoziladi
        report = TranslitReport()
        transliterate_pdf(in_path, out_path, conv, report)
        report.remaining = sum(scan_pdf(out_path, conv).values())
        report.passes = 2   # skan + saqlangan faylni yakuniy tekshirish
        return report
    raise ValueError(f"Qo'llab-quvvatlanmaydigan fayl: {ext}")
