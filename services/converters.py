"""Matnni o'zgartirish qoidalari (konverterlar) — tarjima emas, faqat yozuv/harflar.

Har bir konverter matndagi o'zgartirishlar ro'yxatini beradi:
    (boshlanish, tugash, yangi matn, turi)
Dvigatel (translit_engine) shu ro'yxat asosida faylning asl bo'laklariga (run'lariga)
yozadi — shrift, rang, o'lcham va joylashuv o'zgarmaydi.

Konverterlar:
    NewAlphabetConverter — sh/ch/gʻ/oʻ -> ş/ç/ğ/ö (lotin ichida)
    CyrToLatConverter    — o'zbek kirill -> lotin (oʻ, sh) yoki yangi lotin (ö, ş)
    LatToCyrConverter    — o'zbek lotin (eski yoki yangi) -> kirill
    ScriptStats          — o'zgartirmaydi, faqat yozuv tarkibini sanaydi
"""

import re
from collections import Counter

from services.language import classify_cyrillic, neighbor_contexts
from services.transliteration import (
    APOSTROPHES,
    count_matches,
    iter_matches,
    protected_spans,
    to_new_alphabet,
)

Edit = tuple[int, int, str, str]


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def _is_letter(ch: str) -> bool:
    return bool(ch) and ch.isalpha() and ch not in APOSTROPHES


def _all_caps(text: str, start: int, end: int) -> bool:
    """So'z butunlay katta harfdami (ШАҲАР) — keyingi yoki oldingi harfga qarab."""
    nxt = text[end] if end < len(text) else ""
    if _is_letter(nxt):
        return nxt.isupper()
    prev = text[start - 1] if start > 0 else ""
    return _is_letter(prev) and prev.isupper()


def _apply_case(rep: str, upper: bool, all_caps: bool) -> str:
    if not rep or not upper:
        return rep
    if all_caps:
        return rep.upper()
    return rep[0].upper() + rep[1:]


class Converter:
    """context — qaror qaysi matnga qarab qabul qilinishi (masalan PDF blok matni yoki
    tili aniqlanmagan sarlavha uchun qo'shni paragraf). None — bo'lakning o'zi."""

    def contexts(self, texts: list[str], firsts: list[bool] | None = None) -> list:
        """Hujjat tartibidagi bo'laklar uchun kontekstlar (til hisobga olinmasa — None).

        firsts[i] — bo'lak o'z paragrafining birinchisimi (tab/qator uzilishidan keyingisi emas).
        """
        return [None] * len(texts)

    def split_context(self, context, prev_text: str | None):
        """Paragraf kontekstidan uning ichidagi qator uchun kontekst (PDF qatorlari)."""
        return context

    def for_cells(self) -> "Converter":
        """Excel kataklari va formulalar uchun konverter (ehtiyotkorroq bo'lishi mumkin)."""
        return self

    def edits(self, text: str, context: str | None = None) -> list[Edit]:
        raise NotImplementedError

    def count(self, text: str, context: str | None = None) -> Counter:
        return Counter(edit[3] for edit in self.edits(text, context))

    def convert(self, text: str, context: str | None = None) -> str:
        if not text:
            return text
        out = []
        last = 0
        for start, end, rep, _ in self.edits(text, context):
            out.append(text[last:start])
            out.append(rep)
            last = end
        out.append(text[last:])
        return "".join(out)


# ============================================================ Yangi alifbo (lotin ichida)
class NewAlphabetConverter(Converter):
    def edits(self, text: str, context: str | None = None) -> list[Edit]:
        return [(start, start + 2, rep, kind) for start, kind, rep in iter_matches(text)]

    def count(self, text: str, context: str | None = None) -> Counter:
        return count_matches(text)

    def convert(self, text: str, context: str | None = None) -> str:
        return to_new_alphabet(text)


# ============================================================ Kirill -> Lotin
_CYR_VOWELS = set("аеёиоуэюяўыАЕЁИОУЭЮЯЎЫ")
_CYR_BASE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ч": "ch", "ш": "sh",
    "щ": "sh", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "oʻ", "қ": "q", "ғ": "gʻ", "ҳ": "h",
}
_CYR_NEW = {"ч": "ç", "ш": "ş", "щ": "ş", "ў": "ö", "ғ": "ğ"}
_CYR_LETTERS = frozenset(_CYR_BASE) | {"е", "ц", "ъ"}


class CyrToLatConverter(Converter):
    """O'zbek kirill -> lotin. new=True bo'lsa yangi alifbo (ş, ç, ğ, ö).

    Rus tilidagi paragraflarga TEGILMAYDI. Tili aniqlanmagan qisqa paragraf
    (masalan, "Бухоро") avval qo'shni paragraflarga, ular ham bo'lmasa unknown_is_uz
    ga qarab hal qilinadi — u hujjatdagi o'zbek/rus qismlar nisbatidan olinadi.
    """

    def __init__(self, new: bool = False, unknown_is_uz: bool = True) -> None:
        self.new = new
        self.unknown_is_uz = unknown_is_uz

    def contexts(self, texts: list[str], firsts: list[bool] | None = None) -> list:
        return neighbor_contexts(texts)

    def is_uzbek(self, text: str) -> bool:
        lang = classify_cyrillic(text)
        return lang == "uz" or (lang is None and self.unknown_is_uz)

    def edits(self, text: str, context: str | None = None) -> list[Edit]:
        if not any(c.lower() in _CYR_LETTERS for c in text):
            return []
        if not self.is_uzbek(context if context is not None else text):
            return []                     # rus tilidagi matn — o'girilmaydi
        spans = protected_spans(text)
        out: list[Edit] = []
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            low = ch.lower()
            if low not in _CYR_LETTERS or (spans and _inside(i, spans)):
                i += 1
                continue
            upper = ch.isupper()

            # сҳ — alohida tovushlar: Исҳоқ -> Isʼhoq (yangi alifboda Ishoq)
            if low == "с" and i + 1 < n and text[i + 1].lower() == "ҳ":
                rep = "sh" if self.new else "sʼh"
                out.append((i, i + 2, _apply_case(rep, upper, _all_caps(text, i, i + 2)), "kirill"))
                i += 2
                continue

            prev = text[i - 1] if i > 0 else ""
            if low == "е":
                # So'z boshida, unlidan va ъ/ь dan keyin "ye": ер -> yer, поезд -> poyezd
                at_start = not prev.isalpha()
                rep = "ye" if (at_start or prev in _CYR_VOWELS or prev.lower() in "ъь") else "e"
            elif low == "ц":
                # Unlidan keyin "ts", boshqa joyda "s": милиция -> militsiya, цирк -> sirk
                rep = "ts" if prev in _CYR_VOWELS else "s"
            elif low == "ъ":
                # съезд -> syezd; маъно -> maʼno
                nxt = text[i + 1].lower() if i + 1 < n else ""
                rep = "" if nxt in ("е", "ё", "ю", "я") else "ʼ"
            else:
                rep = (self.new and _CYR_NEW.get(low)) or _CYR_BASE[low]

            out.append((i, i + 1, _apply_case(rep, upper, _all_caps(text, i, i + 1)), "kirill"))
            i += 1
        return out


# ============================================================ Lotin -> Kirill
_LAT_SINGLE = {
    "a": "а", "b": "б", "c": "ц", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п",
    "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "х",
    "y": "й", "z": "з", "ş": "ш", "ç": "ч", "ğ": "ғ", "ö": "ў",
}
_NEW_LETTERS = set("şçğöŞÇĞÖ")
_Y_VOWEL = {"o": "ё", "u": "ю", "a": "я", "e": "е"}
# Rim raqamlari (XVI, II, IV ...) — kirillga o'girilmaydi
_ROMAN_RE = re.compile(
    r"\b(?=[MDCLXVI]+\b)M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})\b"
)


class LatToCyrConverter(Converter):
    """O'zbek lotin (eski: sh, oʻ yoki yangi: ş, ö) -> kirill.

    new_mode: matn yangi alifboda (ş/ç bor) bo'lsa "sh" = s+h (Ishoq -> Исҳоқ).
    None — har bir matn bo'lagi uchun avtomatik aniqlanadi.
    """

    def __init__(self, new_mode: bool | None = None) -> None:
        self.new_mode = new_mode

    def edits(self, text: str, context: str | None = None) -> list[Edit]:
        spans = protected_spans(text) + [(m.start(), m.end()) for m in _ROMAN_RE.finditer(text)]
        new_mode = self.new_mode
        if new_mode is None:
            new_mode = any(c in _NEW_LETTERS for c in text)

        out: list[Edit] = []
        i, n = 0, len(text)
        while i < n:
            if spans and _inside(i, spans):
                i += 1
                continue
            ch = text[i]
            low = ch.lower()
            upper = ch.isupper()
            nxt = text[i + 1] if i + 1 < n else ""
            nxt2 = text[i + 2] if i + 2 < n else ""

            # Tutuq belgisi harflar orasida -> ъ (maʼno -> маъно); qo'shtirnoq bo'lsa tegilmaydi
            if ch in APOSTROPHES:
                prev = text[i - 1] if i > 0 else ""
                if _is_letter(prev) and _is_letter(nxt):
                    out.append((i, i + 1, "ъ", "lotin"))
                i += 1
                continue
            if low not in _LAT_SINGLE:
                i += 1
                continue

            def add(end: int, rep: str) -> None:
                out.append((i, end, _apply_case(rep, upper, _all_caps(text, i, end)), "lotin"))

            if low == "s" and nxt in APOSTROPHES and nxt2.lower() == "h":   # sʼh -> сҳ
                add(i + 3, "сҳ")
                i += 3
            elif low in ("o", "g") and nxt in APOSTROPHES and (low == "g" or _is_letter(nxt2)):
                add(i + 2, "ў" if low == "o" else "ғ")                       # oʻ, gʻ
                i += 2
            elif low in ("s", "c") and nxt.lower() == "h":                   # sh, ch
                add(i + 2, "ч" if low == "c" else ("сҳ" if new_mode else "ш"))
                i += 2
            elif low == "t" and nxt.lower() == "s" and text[i + 2:i + 5].lower() in ("iya", "ion"):
                add(i + 2, "ц")                       # militsiya -> милиция (ketsa -> кетса qoladi)
                i += 2
            elif low == "y" and nxt.lower() in _Y_VOWEL:
                if nxt.lower() == "o" and nxt2 in APOSTROPHES:              # yoʻl -> йўл
                    add(i + 1, "й")
                    i += 1
                else:                                                        # yo, yu, ya, ye
                    add(i + 2, _Y_VOWEL[nxt.lower()])
                    i += 2
            elif low == "e":                                                 # so'z boshida э
                prev = text[i - 1] if i > 0 else ""
                add(i + 1, "е" if _is_letter(prev) else "э")
                i += 1
            else:
                add(i + 1, _LAT_SINGLE[low])
                i += 1
        return out


# ============================================================ Yangi lotin -> eski lotin
_NEW_TO_OLD = {"ş": "sh", "ç": "ch", "ğ": "gʻ", "ö": "oʻ"}


class NewToOldConverter(Converter):
    """Yangi alifbo (ş, ç, ğ, ö) -> eski lotin (sh, ch, gʻ, oʻ).

    Yangi alifbodagi "sh" — alohida s va h (Işoq emas, Ishoq = Isʼhoq), eski
    alifboda tutuq bilan ajratiladi: sʼh.
    """

    def edits(self, text: str, context: str | None = None) -> list[Edit]:
        if _NEW_LETTERS.isdisjoint(text):
            return []
        spans = protected_spans(text)
        out: list[Edit] = []
        for i, ch in enumerate(text):
            if spans and _inside(i, spans):
                continue
            low = ch.lower()
            if low in _NEW_TO_OLD:
                rep = _apply_case(_NEW_TO_OLD[low], ch.isupper(), _all_caps(text, i, i + 1))
                out.append((i, i + 1, rep, "yangi"))
            elif low == "s" and i + 1 < len(text) and text[i + 1].lower() == "h":
                out.append((i, i + 1, ch + "ʼ", "yangi"))
        return out


# ============================================================ Yozuv tarkibi (sanash)
class ScriptStats(Converter):
    """Hech narsani o'zgartirmaydi — yozuv va til tarkibini sanaydi.

    Kalitlar: kirill_uz, kirill_ru, kirill_unk (tili aniqlanmagan), lotin, yangi, eski.
    """

    def contexts(self, texts: list[str], firsts: list[bool] | None = None) -> list:
        return neighbor_contexts(texts)

    def edits(self, text: str, context: str | None = None) -> list[Edit]:
        return []

    def count(self, text: str, context: str | None = None) -> Counter:
        counter: Counter = Counter()
        cyr_key = None
        for ch in text:
            low = ch.lower()
            if low in _CYR_LETTERS:
                if cyr_key is None:
                    lang = classify_cyrillic(context if context is not None else text)
                    cyr_key = {"uz": "kirill_uz", "ru": "kirill_ru"}.get(lang, "kirill_unk")
                counter[cyr_key] += 1
            elif low in _LAT_SINGLE:
                counter["lotin"] += 1
                if ch in _NEW_LETTERS:
                    counter["yangi"] += 1
        old = sum(count_matches(text).values())
        if old:
            counter["eski"] += old
        return counter


NEW_ALPHABET = NewAlphabetConverter()
CYR_TO_LAT = CyrToLatConverter(new=False)
CYR_TO_NEW = CyrToLatConverter(new=True)
SCRIPT_STATS = ScriptStats()
