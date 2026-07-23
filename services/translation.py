"""Fayl tarjimasi: AI tarjima + tuzilmani saqlash.

Til aniqlash tez (AI'siz) heuristika bilan: Kirill -> ru, lotin ichida
o'zbekcha belgilar/so'zlar bo'lsa -> uz, aks holda -> en.
"""

from services.ai import AICorrector

LANGS = ("ru", "uz", "en")
LANG_NAMES = {"ru": "🇷🇺 Rus", "uz": "🇺🇿 Uzbek", "en": "🇬🇧 Ingliz"}

_UZ_MARKERS = [
    "oʻ", "gʻ", "o'", "g'", " va ", " bilan ", " uchun ", " bo'l", " qil",
    " ular", " yoki ", "sh", "ch", " man", " emas", "ligi", "lar ",
]
_EN_MARKERS = [
    " the ", " and ", " of ", " to ", " is ", " in ", " for ", " with ",
    " that ", " this ", " are ", " on ", " it ",
]


def detect_language(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "uz"
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    if cyr / len(letters) > 0.3:
        return "ru"
    low = f" {text.lower()} "
    uz_hits = sum(low.count(m) for m in _UZ_MARKERS)
    en_hits = sum(low.count(m) for m in _EN_MARKERS)
    return "uz" if uz_hits >= en_hits else "en"


def target_languages(source: str) -> list[str]:
    """Manba tilidan boshqa qolgan tillar."""
    return [lang for lang in LANGS if lang != source]


def build_sample(segments: list[str], max_chars: int = 6000) -> str:
    """Til aniqlash uchun BUTUN hujjatdan vakillik namunasi (boshi+o'rtasi+oxiri)."""
    full = " ".join(s for s in segments if s and s.strip())
    if len(full) <= max_chars:
        return full
    part = max_chars // 3
    n = len(full)
    mid = n // 2
    return (
        full[:part]
        + " "
        + full[mid - part // 2: mid + part // 2]
        + " "
        + full[-part:]
    )


class Translator:
    """Fayl processorlari kutgan interfeys: `correct_many(segments)`."""

    def __init__(self, ai: AICorrector, target_lang: str) -> None:
        self.ai = ai
        self.target_lang = target_lang

    async def correct_many(self, segments: list[str]) -> list[str]:
        return await self.ai.translate(segments, self.target_lang)
