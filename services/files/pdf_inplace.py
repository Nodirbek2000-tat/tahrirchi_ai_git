"""PDF'ni asl dizaynida tahrirlash — Word'ga o'tkazmasdan.

O'zgarishi kerak bo'lgan QATORLAR o'chirilib, aynan o'sha joyga, o'sha o'lcham, rang
va shaffoflikda qayta yoziladi. Qatorning boshi va oxiri joyida qoladi: so'z
qisqargan/uzaygan joy qatordagi so'z oraliqlariga teng taqsimlanadi (xuddi ikki
tomonga tekislangan matndagidek) — bo'sh "tirqish" qolmaydi, markazdagi sarlavha
markazda qoladi. Rasm, chiziq, jadval, fon va o'zgarmagan qatorlar tegilmaydi.

Tegilmaydi:
  - ko'rinmas matn (skaner PDF'dagi OCR qatlami) — aks holda yozuv ikki marta ko'rinardi
  - qiya/tik matn — hisobotda "qolgan" sifatida ko'rsatiladi
  - rasm ichidagi yozuv

Shrift: PDF ichidagi shriftlarda odatda faqat ishlatilgan harflar bo'ladi, shuning
uchun qator asl shriftning o'zi (Times New Roman, Arial — serverda o'rnatilgan bo'lsa)
yoki o'lchamlari aynan mos shrift bilan yoziladi (Liberation, Carlito). Shriftdan
faqat kerakli harflar kesib olinadi (subset) — fayl hajmi deyarli o'smaydi.
"""

import io
import logging
import os
import re
import shutil
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass

import fitz

from services.converters import Converter

logger = logging.getLogger(__name__)

_TEXT_FLAGS = fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_MEDIABOX_CLIP
_VISIBLE_FLAGS = 16 | 32     # char_flags: to'ldirilgan yoki konturli matn
_H_MIN_SCALE = 0.88          # shu chegaragacha faqat eniga siqiladi (ko'zga bilinmaydi)
_U_MIN_SCALE = 0.6           # undan ko'p kerak bo'lsa harflar proporsional kichraytiriladi
_WORD_RE = re.compile(r"\S+")
_LEGIT_EXT = set("ğĞşŞıİ")   # Lotin kengaytmasidagi qonuniy harflar


class UnreadablePdfError(Exception):
    """PDF matnini o'qib bo'lmaydi (shrift kodlash xatosi yoki parol)."""

    @property
    def user_text(self) -> str:
        return (
            f"❌ {self}.\n\n"
            "Bunday PDF'dagi harflarni xatosiz o'zgartirib bo'lmaydi. Iloji bo'lsa "
            "asl Word/PowerPoint faylini yuboring.\n🪙 Token yechilmadi."
        )


@dataclass(frozen=True)
class _Style:
    font: str
    size: float
    color: int
    alpha: int
    flags: int


@dataclass
class _Char:
    c: str
    bbox: tuple
    origin: tuple
    style: _Style


@dataclass
class _Line:
    chars: list            # [_Char]
    editable: bool         # gorizontal qatormi
    align: str             # justify | left | center | right
    block: tuple           # blok chegarasi (x0, x1)
    multi: bool            # blokda bir nechta qator bormi
    block_text: str = ""   # butun blok (paragraf) matni — tilni aniqlash uchun


@dataclass
class _Insert:
    point: tuple
    text: str
    size: float
    color: tuple
    opacity: float
    font_path: str
    pivot: tuple
    sx: float               # eniga siqish/cho'zish
    sy: float               # bo'yiga (proporsional kichraytirishda sx bilan teng)


# ============================================================ Shriftlar
_WIN = r"C:\Windows\Fonts"
_MS = "/usr/share/fonts/truetype/msttcorefonts"          # ttf-mscorefonts-installer
_LIB = ("/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/liberation2")
_CROS = "/usr/share/fonts/truetype/crosextra"            # Carlito / Caladea
_DJV = "/usr/share/fonts/truetype/dejavu"
_STYLES = [(False, False), (True, False), (False, True), (True, True)]
_SUFFIX = ["Regular", "Bold", "Italic", "BoldItalic"]
# Haqiqiy Microsoft shriftlari: (Windows / kichik harfli nom, msttcorefonts nomi)
_REAL = {
    "serif": [("times.ttf", "Times_New_Roman.ttf"), ("timesbd.ttf", "Times_New_Roman_Bold.ttf"),
              ("timesi.ttf", "Times_New_Roman_Italic.ttf"),
              ("timesbi.ttf", "Times_New_Roman_Bold_Italic.ttf")],
    "sans": [("arial.ttf", "Arial.ttf"), ("arialbd.ttf", "Arial_Bold.ttf"),
             ("ariali.ttf", "Arial_Italic.ttf"), ("arialbi.ttf", "Arial_Bold_Italic.ttf")],
    "mono": [("cour.ttf", "Courier_New.ttf"), ("courbd.ttf", "Courier_New_Bold.ttf"),
             ("couri.ttf", "Courier_New_Italic.ttf"), ("courbi.ttf", "Courier_New_Bold_Italic.ttf")],
    "calibri": [("calibri.ttf", None), ("calibrib.ttf", None), ("calibrii.ttf", None),
                ("calibriz.ttf", None)],
}
_METRIC = {"calibri": "Carlito", "cambria": "Caladea"}   # o'lchamlari aynan mos
_BASE = {"calibri": "sans", "cambria": "serif"}
_LIBERATION = {"serif": "LiberationSerif", "sans": "LiberationSans", "mono": "LiberationMono"}
_DEJAVU = {"serif": ("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"),
           "sans": ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
           "mono": ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf")}
_font_cache: dict = {}


def _family(style: _Style) -> tuple[str, bool, bool]:
    name = style.font.lower()
    bold = bool(style.flags & 16) or any(k in name for k in ("bold", "black", "heavy", "semibold"))
    italic = bool(style.flags & 2) or "italic" in name or "oblique" in name
    if style.flags & 8 or any(k in name for k in ("courier", "mono", "consolas")):
        return "mono", bold, italic
    if "calibri" in name:
        return "calibri", bold, italic
    if "cambria" in name:
        return "cambria", bold, italic
    if any(k in name for k in ("arial", "helvetica", "verdana", "tahoma", "segoe", "sans", "roboto")):
        return "sans", bold, italic
    return "serif", bold, italic     # hujjatlarda eng ko'p — Times New Roman


def _candidates(family: str, bold: bool, italic: bool) -> list[str]:
    base = _BASE.get(family, family)
    families = [family] if family == base else [family, base]
    paths: list[str] = []
    for b, i in ((bold, italic), (bold, False), (False, False)):
        k = _STYLES.index((b, i))
        for fam in families:
            if fam in _REAL:
                win, ms = _REAL[fam][k]
                paths += [os.path.join(_WIN, win), f"{_MS}/{win}"]
                if ms:
                    paths.append(f"{_MS}/{ms}")
            if fam in _METRIC:
                paths.append(f"{_CROS}/{_METRIC[fam]}-{_SUFFIX[k]}.ttf")
        paths += [f"{lib}/{_LIBERATION[base]}-{_SUFFIX[k]}.ttf" for lib in _LIB]
        if not i:
            paths.append(f"{_DJV}/{_DEJAVU[base][1 if b else 0]}")
    paths.append(f"{_DJV}/DejaVuSans.ttf")      # eng keng qamrovli zaxira
    seen: set = set()
    return [p for p in paths if not (p in seen or seen.add(p))]


def _load_font(path: str):
    if path not in _font_cache:
        font = None
        if os.path.exists(path):
            try:
                font = fitz.Font(fontfile=path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Shrift ochilmadi (%s): %s", path, exc)
        _font_cache[path] = font
    return _font_cache[path]


def _resolve_font(style: _Style, text: str):
    """Matndagi barcha harflarni qo'llaydigan eng mos shrift: (yo'l, fitz.Font) yoki None."""
    for path in _candidates(*_family(style)):
        font = _load_font(path)
        if font and all(font.has_glyph(ord(c)) for c in text if not c.isspace()):
            return path, font
    return None


def _subset_font(path: str, chars: set) -> bytes:
    """Shriftdan faqat kerakli harflarni kesib oladi — fayl hajmi o'smaydi."""
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont

        font = TTFont(path)
        opts = subset.Options()
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        opts.hinting = False
        opts.drop_tables += ["meta"]
        subsetter = subset.Subsetter(opts)
        subsetter.populate(unicodes={ord(c) for c in chars} | {32})
        subsetter.subset(font)
        buf = io.BytesIO()
        font.save(buf)
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Shrift kesilmadi, to'liq joylanadi (%s): %s", path, exc)
        with open(path, "rb") as f:
            return f.read()


# ============================================================ Matnni o'qish
@contextmanager
def _unrotated(page):
    rotation = page.rotation
    if rotation:
        page.set_rotation(0)
    try:
        yield
    finally:
        if rotation:
            page.set_rotation(rotation)


def _is_visible(span) -> bool:
    if span.get("alpha", 255) == 0:
        return False
    flags = span.get("char_flags")
    return flags is None or bool(flags & _VISIBLE_FLAGS)


def _is_horizontal(line) -> bool:
    dx, dy = line.get("dir", (1, 0))
    return dx > 0.999 and abs(dy) < 0.001 and not line.get("wmode", 0)


def _block_alignment(lines: list, bx0: float, bx1: float, page_left: float,
                     page_right: float) -> str:
    """Blok qatorlarining chekka masofalariga qarab tekislanishni aniqlaydi."""
    if len(lines) == 1:
        x0, x1 = lines[0]["bbox"][0], lines[0]["bbox"][2]
        centered = abs((x0 + x1) / 2 - (page_left + page_right) / 2) < 3 and x0 > page_left + 5
        return "center" if centered else "left"
    tol = 1.5
    margins = [(ln["bbox"][0] - bx0, bx1 - ln["bbox"][2]) for ln in lines]
    full = [lm < tol and rm < tol for lm, rm in margins]
    centered = [lm > 2 and abs(lm - rm) < 2 for lm, rm in margins]
    if any(centered) and all(c or f for c, f in zip(centered, full)):
        return "center"
    if all(full[:-1]):
        return "justify"
    if all(rm < tol for _, rm in margins) and any(lm > 2 for lm, _ in margins):
        return "right"
    return "left"


def _page_lines(page) -> list[_Line]:
    """Ko'rinadigan matn qatorlari (tekislanishi bilan).

    Ko'rinmas span'lar qatorni bo'ladi va o'tkazib yuboriladi; qiya/tik qatorlar
    tahrirlanmaydi.
    """
    data = page.get_text("rawdict", flags=_TEXT_FLAGS)
    blocks = [b for b in data.get("blocks", []) if b.get("lines")]
    hor = [ln for b in blocks for ln in b["lines"] if _is_horizontal(ln)]
    page_left = min((ln["bbox"][0] for ln in hor), default=0.0)
    page_right = max((ln["bbox"][2] for ln in hor), default=0.0)

    result = []
    for block in blocks:
        hlines = [ln for ln in block["lines"] if _is_horizontal(ln)]
        bx0, bx1 = block["bbox"][0], block["bbox"][2]
        align = _block_alignment(hlines, bx0, bx1, page_left, page_right) if hlines else "left"
        multi = len(hlines) > 1
        first = len(result)
        for line in block["lines"]:
            horizontal = _is_horizontal(line)
            line_align = align
            if align == "justify" and hlines and line is hlines[-1]:
                line_align = "left"            # paragrafning oxirgi qatori
            seg: list[_Char] = []

            def flush():
                if seg:
                    result.append(_Line(list(seg), horizontal, line_align, (bx0, bx1), multi))
                    seg.clear()

            for span in line.get("spans", []):
                if not _is_visible(span):
                    flush()
                    continue
                style = _Style(span["font"], span["size"], span["color"],
                               span.get("alpha", 255), span["flags"])
                for ch in span["chars"]:
                    seg.append(_Char(ch["c"], tuple(ch["bbox"]), tuple(ch["origin"]), style))
            flush()
        block_text = " ".join("".join(ch.c for ch in ln.chars) for ln in result[first:])
        for ln in result[first:]:
            ln.block_text = block_text
    return result


def _line_contexts(lines: list[_Line], conv: Converter) -> list[str]:
    """Har qator uchun kontekst: o'z bloki yoki (til aniqlanmasa) qo'shni blok matni."""
    blocks = list(dict.fromkeys(ln.block_text for ln in lines))
    resolved = dict(zip(blocks, conv.contexts(blocks)))
    return [resolved[ln.block_text] or ln.block_text for ln in lines]


def _bad_chars(lines: list[_Line]) -> tuple[int, int]:
    """(jami harf, buzuq kodlangan harf) — shrift ToUnicode xatosini aniqlash uchun."""
    total = bad = 0
    for line in lines:
        for ch in line.chars:
            c = ch.c
            if c.isspace():
                continue
            total += 1
            code = ord(c)
            if (c == "\ufffd" or 0xE000 <= code <= 0xF8FF
                    or (0x0100 <= code <= 0x024F and c not in _LEGIT_EXT)):
                bad += 1
    return total, bad


def _check_readable(total: int, bad: int) -> None:
    if total >= 50 and bad / total > 0.3:
        raise UnreadablePdfError("PDF matni buzuq kodlangan")


def _open(path: str):
    doc = fitz.open(path)
    if doc.needs_pass:
        doc.close()
        raise UnreadablePdfError("PDF parol bilan himoyalangan")
    return doc


def scan_pdf(path: str, conv: Converter) -> Counter:
    """Ko'rinadigan matndagi o'zgartiriladigan joylar soni."""
    counter: Counter = Counter()
    total = bad = 0
    doc = _open(path)
    try:
        for page in doc:
            with _unrotated(page):
                lines = _page_lines(page)
            t, b = _bad_chars(lines)
            total += t
            bad += b
            for line, ctx in zip(lines, _line_contexts(lines, conv)):
                counter.update(conv.count("".join(ch.c for ch in line.chars), ctx))
    finally:
        doc.close()
    _check_readable(total, bad)
    return counter


# ============================================================ Qatorni rejalashtirish
def _rgb(color: int) -> tuple:
    return ((color >> 16) & 255) / 255, ((color >> 8) & 255) / 255, (color & 255) / 255


def _fit(words_new: float, old_gaps: list, width: float, size: float) -> tuple[list, float]:
    """So'zlarni berilgan kenglikka joylash: (yangi oraliqlar, kerakli siqish koeffitsienti)."""
    if not old_gaps:
        if words_new > width > 0:
            return [], width / words_new
        return [], 1.0
    room = width - words_new
    if room >= sum(old_gaps):
        # Joy ortdi: barcha oraliqlarga teng taqsimlanadi (ikki tomonga tekislash)
        return [g + (room - sum(old_gaps)) / len(old_gaps) for g in old_gaps], 1.0
    min_gap = 0.12 * size
    if room >= min_gap * len(old_gaps) and sum(old_gaps) > 0:
        k = room / sum(old_gaps)                 # oraliqlar qisqaradi
        return [g * k for g in old_gaps], 1.0
    gaps = [min_gap] * len(old_gaps)             # yetmasa so'zlar siqiladi
    return gaps, (width - min_gap * len(gaps)) / words_new


def _scales(needed: float) -> tuple[float, float]:
    """Kerakli siqishdan (eniga, bo'yiga) koeffitsientlar."""
    if needed >= 0.999:
        return 1.0, 1.0
    if needed >= _H_MIN_SCALE:
        return needed, 1.0                       # sezilmas darajada eniga siqish
    s = max(_U_MIN_SCALE, needed)
    return s, s                                  # proporsional kichraytirish — cho'zilmaydi


def _plan_line(line: _Line, edits: list):
    """Qatorni qayta yozish rejasi: (o'chiriladigan to'rtburchak, yoziladigan bo'laklar).

    Mos shrift topilmasa None — qatorga tegilmaydi.
    """
    seg = line.chars
    text = "".join(c.c for c in seg)
    new: list = [c.c for c in seg]
    for start, end, rep, _ in edits:
        new[start] = rep
        for pos in range(start + 1, end):
            new[pos] = None

    words = []   # har so'z: (asl boshi, asl oxiri, yangi kenglik, bo'laklar)
    for match in _WORD_RE.finditer(text):
        ws, we = match.span()
        pieces: list = []
        for ch, content in zip(seg[ws:we], new[ws:we]):
            if content is None:
                continue
            if pieces and pieces[-1][0] == ch.style:
                pieces[-1][1].append(content)
            else:
                pieces.append((ch.style, [content], ch))
        resolved = []
        for style, parts, first in pieces:
            piece_text = "".join(parts)
            if not piece_text:
                continue
            found = _resolve_font(style, piece_text)
            if found is None:
                return None
            path, font = found
            resolved.append((style, piece_text, first, path,
                             font.text_length(piece_text, fontsize=style.size)))
        chars = seg[ws:we]
        words.append((chars[0].origin[0], max(c.bbox[2] for c in chars),
                      sum(r[4] for r in resolved), resolved, chars[0].origin[1]))
    if not words:
        return None

    sizes = [c.style.size for c in seg if not c.c.isspace()]
    size = sorted(sizes)[len(sizes) // 2]
    left, right = words[0][0], max(w[1] for w in words)
    span = right - left
    words_new = sum(w[2] for w in words)
    n = len(words)
    old_gaps = [max(0.0, words[i + 1][0] - words[i][1]) for i in range(n - 1)]
    natural = words_new + sum(old_gaps)          # oraliqlar o'zgarmasa qator kengligi
    bx0, bx1 = line.block
    tol = 0.1 * size

    if line.align == "justify":
        # Qatorning boshi va oxiri joyida qoladi
        gaps, needed = _fit(words_new, old_gaps, span, size)
        sx, sy = _scales(needed)
        start = left
    else:
        # Joy chegarasi: ko'p qatorli blokda blok chekkasigacha, aks holda asl qator
        if line.align == "left":
            lo, hi = left, (bx1 if line.multi else right + tol)
        elif line.align == "right":
            lo, hi = (bx0 if line.multi else left - tol), right
        else:  # center
            half = ((bx1 - bx0) - span) / 2 if line.multi else tol
            lo, hi = left - max(half, 0.0), right + max(half, 0.0)
        if natural <= hi - lo:
            gaps, sx, sy = old_gaps, 1.0, 1.0
        else:
            gaps, needed = _fit(words_new, old_gaps, hi - lo, size)
            sx, sy = _scales(needed)
        line_width = words_new * sx + sum(gaps)
        if line.align == "left":
            start = left
        elif line.align == "right":
            start = right - line_width
        else:
            start = (left + right) / 2 - line_width / 2
        start = min(max(start, lo), max(lo, hi - line_width))

    inserts = []
    x = start
    for idx, (_, _, width, resolved, base_y) in enumerate(words):
        px = x
        for j, (style, piece_text, first, path, piece_width) in enumerate(resolved):
            if idx < n - 1 and j == len(resolved) - 1 and gaps[idx] > 0.05:
                # HAQIQIY bo'shliq belgisi: ko'rinmaydi (keyingi so'z o'z joyida turadi),
                # lekin nusxa ko'chirish/qidiruvda so'zlar ajralib turadi
                piece_text += " "
            inserts.append(_Insert(
                point=(px, first.origin[1]), text=piece_text, size=style.size,
                color=_rgb(style.color), opacity=style.alpha / 255, font_path=path,
                pivot=(x, base_y), sx=sx, sy=sy,
            ))
            px += piece_width
        x += width * sx + (gaps[idx] if idx < n - 1 else 0)

    # O'chirish to'rtburchagi: qator harflarining markaz chizig'i bo'ylab tasma —
    # qo'shni qatorlarga tegmaydi
    ink = [c for c in seg if not c.c.isspace()]
    centers = [(c.bbox[1] + c.bbox[3]) / 2 for c in ink]
    x0 = min(c.bbox[0] for c in ink)
    x1 = max(c.bbox[2] for c in ink)
    pad = 0.1 if x1 - x0 > 0.5 else 0.0
    rect = fitz.Rect(x0 + pad, min(centers) - 0.12 * size, x1 - pad, max(centers) + 0.12 * size)
    return rect, inserts


# ============================================================ Asosiy funksiya
def transliterate_pdf(in_path: str, out_path: str, conv: Converter, report) -> None:
    """PDF'ni asl dizaynida o'giradi. report — TranslitReport (found/converted to'ldiriladi)."""
    doc = _open(in_path)
    try:
        # 1-o'tish: tahlil va reja (fayl hali o'zgarmaydi)
        plans: dict = {}
        chars_by_font: dict = defaultdict(set)
        total = bad = 0
        for page in doc:
            with _unrotated(page):
                lines = _page_lines(page)
            t, b = _bad_chars(lines)
            total += t
            bad += b
            rects, inserts = [], []
            for line, ctx in zip(lines, _line_contexts(lines, conv)):
                edits = conv.edits("".join(ch.c for ch in line.chars), ctx)
                if not edits:
                    continue
                report.found.update(e[3] for e in edits)
                if not line.editable:
                    continue
                planned = _plan_line(line, edits)
                if planned is None:
                    continue
                rect, line_inserts = planned
                rects.append(rect)
                inserts.extend(line_inserts)
                for ins in line_inserts:
                    chars_by_font[ins.font_path].update(ins.text)
                report.converted += len(edits)
            if rects:
                plans[page.number] = (rects, inserts)
        _check_readable(total, bad)

        if not plans:
            doc.close()
            shutil.copyfile(in_path, out_path)   # o'zgarish yo'q — fayl aynan o'zi
            return

        # Shriftlardan faqat kerakli harflar
        buffers = {path: _subset_font(path, chars) for path, chars in chars_by_font.items()}
        names = {path: f"TahF{i}" for i, path in enumerate(buffers)}
        fonts = {path: fitz.Font(fontbuffer=buf) for path, buf in buffers.items()}

        # 2-o'tish: eski qatorlarni o'chirish va yangisini o'sha joyga yozish
        for page_no, (rects, inserts) in plans.items():
            page = doc[page_no]
            with _unrotated(page):
                for rect in rects:
                    page.add_redact_annot(rect, fill=False, cross_out=False)
                page.apply_redactions(
                    images=fitz.PDF_REDACT_IMAGE_NONE,
                    graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                    text=fitz.PDF_REDACT_TEXT_REMOVE,
                )
                # Oddiy so'zlar bir xil rang/shaffoflik bo'yicha bitta blokka yig'iladi
                # (fayl hajmi kichik); siqilgan qatorlar alohida yoziladi
                writers: dict = {}
                registered: set = set()
                for ins in inserts:
                    if abs(ins.sx - 1) <= 0.001 and abs(ins.sy - 1) <= 0.001:
                        key = (ins.color, round(ins.opacity, 3))
                        writer = writers.get(key)
                        if writer is None:
                            writer = writers[key] = fitz.TextWriter(page.rect)
                        writer.append(ins.point, ins.text, font=fonts[ins.font_path],
                                      fontsize=ins.size)
                        continue
                    name = names[ins.font_path]
                    if name not in registered:
                        page.insert_font(fontname=name, fontbuffer=buffers[ins.font_path])
                        registered.add(name)
                    page.insert_text(
                        ins.point, ins.text, fontsize=ins.size, fontname=name,
                        color=ins.color, fill_opacity=ins.opacity,
                        morph=(fitz.Point(ins.pivot), fitz.Matrix(ins.sx, ins.sy)),
                    )
                for (color, opacity), writer in writers.items():
                    writer.write_text(page, color=color, opacity=opacity)
        doc.save(out_path, garbage=1, deflate=True)
    finally:
        if not doc.is_closed:
            doc.close()
