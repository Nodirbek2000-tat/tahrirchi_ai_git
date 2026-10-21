"""Yangi o'zbek lotin alifbosiga deterministik o'girish (AI'siz).

    sh / Sh / SH  -> ş / Ş
    ch / Ch / CH  -> ç / Ç
    gʻ / Gʻ       -> ğ / Ğ
    oʻ / Oʻ       -> ö / Ö

Qoidalar:
- Tutuq belgisining barcha ko'rinishlari taniladi (ʻ ʼ ‘ ’ ' ` ´ va boshqalar).
- oʻ faqat undan keyin harf kelsa o'giriladi — so'z oxiridagi yopuvchi
  qo'shtirnoq ("radio'") adashib ö ga aylanmaydi.
- Havola (https://..., www...) va email ichidagi harflarga tegilmaydi.
"""

import re
from collections import Counter
from collections.abc import Iterator

# g' va o' dagi tutuq belgisining barcha ko'rinishlari
APOSTROPHES = "ʻʼ‘’'`´ʹ′ˈ‛ʽꞌ"

_DIGRAPH_RE = re.compile(
    rf"[sS][hH]|[cC][hH]|[gG][{APOSTROPHES}]|[oO][{APOSTROPHES}](?=[^\W\d_])"
)
_PROTECTED_RE = re.compile(r"(?:https?://|www\.)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

KINDS = ("sh", "ch", "gʻ", "oʻ")
_KIND = {"s": "sh", "c": "ch", "g": "gʻ", "o": "oʻ"}
_MAP = {
    "s": ("Ş", "ş"),
    "c": ("Ç", "ç"),
    "g": ("Ğ", "ğ"),
    "o": ("Ö", "ö"),
}


def protected_spans(text: str) -> list[tuple[int, int]]:
    """Tegilmaydigan joylar: havolalar (https://, www.) va emaillar."""
    if "@" in text or "://" in text or "www." in text:
        return [(m.start(), m.end()) for m in _PROTECTED_RE.finditer(text)]
    return []


def iter_matches(text: str) -> Iterator[tuple[int, str, str]]:
    """Matndagi har bir o'giriladigan juftlik: (boshlanish, turi, yangi harf).

    Har bir moslik aynan 2 belgi: harf + (h yoki tutuq).
    """
    protected = protected_spans(text)
    for m in _DIGRAPH_RE.finditer(text):
        start = m.start()
        if protected and any(a <= start < b for a, b in protected):
            continue
        first = text[start]
        upper, lower = _MAP[first.lower()]
        yield start, _KIND[first.lower()], upper if first.isupper() else lower


def count_matches(text: str) -> Counter:
    return Counter(kind for _, kind, _ in iter_matches(text))


def to_new_alphabet(text: str) -> str:
    if not text:
        return text
    out = []
    last = 0
    for start, _, replacement in iter_matches(text):
        out.append(text[last:start])
        out.append(replacement)
        last = start + 2
    out.append(text[last:])
    return "".join(out)
