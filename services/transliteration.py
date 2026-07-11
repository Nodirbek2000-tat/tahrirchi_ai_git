"""Yangi o'zbek lotin alifbosiga deterministik o'girish.

    sh / Sh / SH  -> ş / Ş
    ch / Ch / CH  -> ç / Ç
    gʻ / Gʻ       -> ğ / Ğ
    oʻ / Oʻ       -> ö / Ö

Bu qism AI'ga bog'liq emas — 100% ishonchli va tez ishlaydi.
"""

import re

# g' va o' dagi tutuq belgisining barcha ko'rinishlari
_APOSTROPHES = "ʻʼ‘’'`´"

_DIGRAPH_RE = re.compile(rf"[sS][hH]|[cC][hH]|[gG][{_APOSTROPHES}]|[oO][{_APOSTROPHES}]")

_MAP = {
    "s": ("Ş", "ş"),
    "c": ("Ç", "ç"),
    "g": ("Ğ", "ğ"),
    "o": ("Ö", "ö"),
}


def _replace(match: re.Match) -> str:
    token = match.group(0)
    upper, lower = _MAP[token[0].lower()]
    # Birinchi harf katta bo'lsa -> katta harf, aks holda kichik
    return upper if token[0].isupper() else lower


def to_new_alphabet(text: str) -> str:
    if not text:
        return text
    return _DIGRAPH_RE.sub(_replace, text)
