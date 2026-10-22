"""Yuborilgan matnni boshqa yozuvga o'girish (imlo va mazmun o'zgarmaydi).

Maqsadlar:
    new — yangi lotin (ş, ç, ğ, ö): eski lotin ham, o'zbek kirill ham o'giriladi
    old — eski lotin (sh, ch, gʻ, oʻ): yangi lotin ham, o'zbek kirill ham o'giriladi
    cyr — o'zbek kirill: lotin (eski yoki yangi) o'giriladi
Ruscha qatorlarga tegilmaydi (services/language.py aniqlaydi).
"""

from services.converters import (
    NEW_ALPHABET,
    Converter,
    CyrToLatConverter,
    LatToCyrConverter,
    NewToOldConverter,
)
from services.language import resolve_languages
from services.transliteration import count_matches

TARGET_LABELS = {
    "new": "Yangi lotin (ş, ö)",
    "old": "Eski lotin (sh, oʻ)",
    "cyr": "Кирилл (ўзбек)",
}
_NEW = frozenset("şçğöŞÇĞÖ")
_TO_OLD = NewToOldConverter()


def _apply(text: str, conv: Converter) -> str:
    lines = text.split("\n")
    return "\n".join(conv.convert(line, ctx) for line, ctx in zip(lines, conv.contexts(lines)))


def analyze(text: str) -> dict:
    """Matn tarkibi: o'zbek kirill, rus, eski/yangi lotin qatorlari bormi."""
    langs = resolve_languages(text.split("\n"))
    new_letters = sum(1 for c in text if c in _NEW)
    old_digraphs = sum(count_matches(text).values())
    return {
        "uz_cyr": "uz_cyr" in langs,
        "ru": "ru" in langs,
        "lat": "uz_lat" in langs or "en" in langs,
        "lat_new": new_letters > old_digraphs,
    }


def default_target(info: dict) -> str | None:
    """Birinchi ko'rsatiladigan natija. None — o'giriladigan narsa yo'q (masalan, ruscha)."""
    if info["uz_cyr"]:
        return "new"
    if info["lat"]:
        return "old" if info["lat_new"] else "new"
    return None


def convert(text: str, target: str) -> str:
    # Avval lotin qismlar, keyin kirill: kirilldan chiqqan matn qayta o'girilmasin
    # (Исҳоқ -> Ishoq; uni yangi alifbo "Işoq" ga aylantirib yubormasligi kerak)
    if target == "new":
        text = _apply(text, NEW_ALPHABET)
        return _apply(text, CyrToLatConverter(new=True))
    if target == "old":
        text = _apply(text, _TO_OLD)
        return _apply(text, CyrToLatConverter(new=False))
    if target == "cyr":
        return _apply(text, LatToCyrConverter(new_mode=None))   # har qator uchun o'zi aniqlaydi
    return text
