"""Imlo tuzatuvchi konverter — translit_engine bilan ishlaydi (shrift/uslub saqlanadi).

Har bir paragraf: tili aniqlanadi (o'zbek lotin / o'zbek kirill; rus va ingliz
matnga tegilmaydi) -> qoidalar (rules.fix) -> AI tuzatgan murakkab gaplar
(ai_fixes, ixtiyoriy) -> asl matn bilan farqi belgi darajasidagi tahrirlar.
"""

from dataclasses import dataclass, replace
from difflib import SequenceMatcher

from services.converters import Converter, Edit
from services.language import resolve_languages
from services.spelling import rules
from services.spelling.lexicon import get_lexicon
from services.transliteration import APOSTROPHES

KIND_LABELS = {
    "tinish": "tinish belgisi",
    "vergul": "vergul",
    "katta_harf": "katta harf",
    "tutuq": "tutuq/oʻ, gʻ",
    "qoshtirnoq": "qo'shtirnoq",
    "tire": "tire",
    "aralash": "aralash harf",
    "soz": "so'z imlosi",
}
_UZ = ("uz_lat", "uz_cyr")
_SPACE_PUNCT = frozenset("  .;:!?…")
_QUOTES = frozenset('"«»“”„')
_DASHES = frozenset("—–-")
_HOMO = frozenset("aceopxyABCEHKMOPTXYасеорхуАВСЕНКМОРТХУ")
_TUTUQ_CHARS = frozenset(APOSTROPHES + "ъЪ")


@dataclass(frozen=True)
class SpellCtx:
    lang: str | None      # "uz_lat" | "uz_cyr" | None (tegilmaydi)
    starts: bool = True   # yangi gap bilan boshlanadimi (katta harf uchun)


def _kind(old: str, new: str) -> str:
    # Qo'shish oldingi belgiga biriktirilgan ("k" -> "k,") — faqat farqli qism baholanadi
    p = 0
    while p < len(old) and p < len(new) and old[p] == new[p]:
        p += 1
    s = 0
    while s < len(old) - p and s < len(new) - p and old[-1 - s] == new[-1 - s]:
        s += 1
    old, new = old[p:len(old) - s], new[p:len(new) - s]
    if old != new and old.lower() == new.lower():
        return "katta_harf"
    chars = set(old) | set(new)
    if "," in chars and chars <= _SPACE_PUNCT | {","}:
        return "vergul"
    if chars <= _SPACE_PUNCT:
        return "tinish"
    if chars & _QUOTES:
        return "qoshtirnoq"
    if chars & _DASHES and chars <= _DASHES | {" "}:
        return "tire"
    if len(old) == len(new) and all(a == b or (a in _HOMO and b in _HOMO)
                                    for a, b in zip(old, new)):
        return "aralash"
    if chars & _TUTUQ_CHARS and set(new) - set(old) <= _TUTUQ_CHARS | {"ʻ"}:
        return "tutuq"
    return "soz"


def diff_edits(old: str, new: str) -> list[Edit]:
    """Ikki matn farqi -> tahrirlar. Qo'shish oldingi belgiga biriktiriladi
    (vergul o'zidan oldingi so'zning shriftini oladi)."""
    if not old:
        return []
    out: list[list] = []
    prefix = ""   # matn boshiga qo'shilgan belgilar — birinchi belgiga biriktiriladi
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        rep = new[j1:j2]
        if i1 == i2:   # faqat qo'shish
            if out and out[-1][1] == i1:
                out[-1][2] += rep
            elif i1 > 0:
                out.append([i1 - 1, i1, old[i1 - 1] + rep])
            else:
                prefix += rep
        elif out and out[-1][1] == i1:
            out[-1][1] = i2
            out[-1][2] += rep
        else:
            out.append([i1, i2, rep])
    if prefix:
        if out and out[0][0] == 0:
            out[0][2] = prefix + out[0][2]
        else:
            out.insert(0, [0, 1, prefix + old[0]])
            if len(out) > 1 and out[1][0] == 1:   # tegib turgan tahrir — birlashtiriladi
                nxt = out.pop(1)
                out[0][1] = nxt[1]
                out[0][2] += nxt[2]
    return [(a, b, rep, _kind(old[a:b], rep)) for a, b, rep in out]


class SpellConverter(Converter):
    def __init__(self, ai_fixes: dict[str, str] | None = None, unknown_is_uz: bool = True,
                 quotes: dict | None = None, dash: str = "—", cells: bool = False,
                 lexicon=None) -> None:
        self.ai_fixes = ai_fixes or {}
        self.unknown_is_uz = unknown_is_uz
        self.quotes = quotes or {}
        self.dash = dash
        self.cells = cells
        self.lexicon = lexicon if lexicon is not None else get_lexicon()
        self._cache: dict = {}
        self._cells_conv = None

    # ------------------------------------------------------------ kontekst
    def contexts(self, texts: list[str], firsts: list[bool] | None = None) -> list[SpellCtx]:
        langs = resolve_languages(texts, self.unknown_is_uz)
        out = []
        prev = None
        for i, (text, lang) in enumerate(zip(texts, langs)):
            first = firsts[i] if firsts is not None else True
            if first:
                starts = prev is None or rules.ends_sentence(prev) or _heading_like(prev)
            else:
                starts = rules.ends_sentence(prev)
            out.append(SpellCtx(lang if lang in _UZ else None, starts))
            if text.strip():
                prev = text
        return out

    def split_context(self, ctx, prev_text: str | None):
        if not isinstance(ctx, SpellCtx) or prev_text is None:
            return ctx
        return replace(ctx, starts=rules.ends_sentence(prev_text))

    def for_cells(self) -> "SpellConverter":
        if self.cells:
            return self
        if self._cells_conv is None:
            self._cells_conv = SpellConverter(
                unknown_is_uz=self.unknown_is_uz, cells=True, lexicon=self.lexicon
            )
        return self._cells_conv

    # ------------------------------------------------------------ tuzatish
    def _ctx(self, text: str, context) -> SpellCtx:
        if isinstance(context, SpellCtx):
            return context
        lang = resolve_languages([text], self.unknown_is_uz)[0]
        return SpellCtx(lang if lang in _UZ else None, True)

    def rule_fix(self, text: str, ctx: SpellCtx) -> str:
        if ctx.lang is None:
            return text
        return rules.fix(text, ctx.lang, ctx.starts, self.cells, self.lexicon,
                         self.quotes.get(ctx.lang), self.dash)

    def apply_ai(self, text: str) -> str:
        if not self.ai_fixes or self.cells:
            return text
        parts, last = [], 0
        for a, b in rules.split_sentences(text):
            fixed = self.ai_fixes.get(text[a:b])
            if fixed is not None:
                parts.append(text[last:a])
                parts.append(fixed)
                last = b
        if not parts:
            return text
        parts.append(text[last:])
        return "".join(parts)

    def edits(self, text: str, context=None) -> list[Edit]:
        ctx = self._ctx(text, context)
        if ctx.lang is None or not text:
            return []
        key = (text, ctx)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        new = self.apply_ai(self.rule_fix(text, ctx))
        result = diff_edits(text, new) if new != text else []
        if len(self._cache) < 200_000:
            self._cache[key] = result
        return result


class StyleStats(Converter):
    """O'zgartirmaydi — hujjatda qaysi qo'shtirnoq («» yoki “”) va tire (— yoki –)
    ko'proq ishlatilganini sanaydi: yangi belgilar hujjat uslubiga moslanadi."""

    def edits(self, text: str, context=None) -> list[Edit]:
        return []

    def count(self, text: str, context=None):
        from collections import Counter
        return Counter({
            "guil": text.count("«"), "curly": text.count("“"),
            "em": text.count(" — "), "en": text.count(" – "),
        })


def styles(stats) -> tuple[dict, str]:
    """StyleStats natijasidan (qo'shtirnoqlar, tire)."""
    if stats.get("guil", 0) > stats.get("curly", 0):
        quotes = {"uz_lat": "«»", "uz_cyr": "«»"}
    elif stats.get("curly", 0) > stats.get("guil", 0):
        quotes = {"uz_lat": "“”", "uz_cyr": "“”"}
    else:
        quotes = {}
    dash = "–" if stats.get("en", 0) > stats.get("em", 0) else "—"
    return quotes, dash


def _heading_like(text: str) -> bool:
    """Qisqa sarlavha (nuqtasiz) — keyingi paragraf yangi gap bilan boshlanadi."""
    t = text.strip()
    return bool(t) and len(t.split()) <= 6 and t[-1] not in ",;:-–—("
