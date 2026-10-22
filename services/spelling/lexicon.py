"""O'zbek so'zlari lug'ati (lotin + kirill) — imlo xatolarini AI'siz topish uchun.

Fayllar: services/spelling/data/uz_lat.txt.gz va uz_cyr.txt.gz ("so'z\\tchastota").
Lug'at O'zbek Vikipediyasi matnlaridan yasalgan (tools/build_lexicon.py).

suggest(word) — faqat KLAVIATURA xatolarini tuzatadi va faqat aniq bo'lsa:
  lotin: x↔h (xozir→hozir), k→q (kilish→qilish), oʻ/gʻ belgisi tushib qolgan
         (ozbek→oʻzbek), tutuq tushib qolgan (malumot→maʼlumot)
  kirill: у→ў, к→қ, г→ғ, х→ҳ (Узбекистон→Ўзбекистон, хам→ҳам), ъ tushib qolgan
Shartlar: asl so'z lug'atda YO'Q, variant lug'atda ko'p uchraydi va ikkinchi
variantdan kamida 3 barobar ko'p — aks holda so'zga tegilmaydi.
"""

import gzip
import itertools
import logging
import os
import threading

logger = logging.getLogger(__name__)

_DIR = os.path.join(os.path.dirname(__file__), "data")
_FILES = {"lat": "uz_lat.txt.gz", "cyr": "uz_cyr.txt.gz"}

OKINA = "ʻ"
TUTUQ = "ʼ"
_NEW_TO_OLD = str.maketrans({"ş": "sh", "ç": "ch", "ğ": "g" + OKINA, "ö": "o" + OKINA})
_NEW_LETTERS = frozenset("şçğö")

_MIN_FREQ = 5        # tavsiya qilinadigan so'z lug'atda kamida shuncha uchrashi kerak
_RATIO = 3           # eng yaxshi variant ikkinchisidan shuncha barobar ko'p bo'lsin
_TYPO_RATIO = 30     # lug'atda bor so'z ham xato hisoblanadi, agar to'g'ri varianti
                     # shuncha barobar ko'p uchrasa (Vikipediyadagi "xozir" kabi xatolar)
_KNOWN_FREQ = 3      # shuncha va undan ko'p uchragan so'z "ma'lum" (AI'ga shubha emas)
_MAX_POSITIONS = 8   # o'zgartirish mumkin bo'lgan joylar (variantlar soni cheklanadi)

_LAT_VOWELS = frozenset("aeiou")
_CYR_VOWELS = frozenset("аеёиоуэюяў")
_CYR_SWAP = {"у": "ў", "к": "қ", "г": "ғ", "х": "ҳ"}


def _load(path: str) -> dict[str, int]:
    words: dict[str, int] = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            word, _, freq = line.rstrip("\n").partition("\t")
            if word:
                words[word] = int(freq or 1)
    return words


class Lexicon:
    """paths — {"lat": fayl, "cyr": fayl}; har bir yozuv lug'ati birinchi kerak bo'lganda yuklanadi."""

    def __init__(self, paths: dict[str, str] | None = None, words: dict | None = None) -> None:
        self._paths = paths or {}
        self._loaded: dict[str, dict[str, int]] = dict(words or {})
        self._suggest_cache: dict = {}
        self._lock = threading.Lock()

    def words(self, script: str) -> dict[str, int]:
        words = self._loaded.get(script)
        if words is None:
            with self._lock:
                words = self._loaded.get(script)
                if words is None:
                    path = self._paths.get(script)
                    words = _load(path) if path else {}
                    self._loaded[script] = words
                    logger.info("Lug'at yuklandi (%s): %s so'z", script, len(words))
        return words

    def freq(self, word: str, script: str) -> int:
        if script == "lat" and not _NEW_LETTERS.isdisjoint(word):
            word = word.translate(_NEW_TO_OLD)
        return self.words(script).get(word, 0)

    def known(self, word: str, script: str) -> bool:
        return self.freq(word.lower(), script) >= _KNOWN_FREQ

    # ------------------------------------------------------------ variantlar
    @staticmethod
    def _lat_edits(word: str) -> list[tuple[int, int, str]]:
        """(boshlanish, tugash, yangi) — mumkin bo'lgan bitta o'zgartirishlar."""
        edits = []
        n = len(word)
        for i, ch in enumerate(word):
            nxt = word[i + 1] if i + 1 < n else ""
            if ch == "x":
                edits.append((i, i + 1, "h"))
            elif ch == "h" and (i == 0 or word[i - 1] not in "sc"):
                edits.append((i, i + 1, "x"))
            elif ch == "k":
                edits.append((i, i + 1, "q"))
            if ch in "og" and nxt and nxt != OKINA and (ch == "g" or nxt.isalpha()):
                edits.append((i + 1, i + 1, OKINA))
            if ch == "g" and not nxt:
                edits.append((n, n, OKINA))
            # Tutuq: unlidan keyin (eʼtibor, maʼlumot) yoki undoshdan keyin unli oldidan (sanʼat)
            if nxt and nxt.isalpha() and nxt not in (OKINA, TUTUQ) and ch not in "og" and (
                    (ch in _LAT_VOWELS and nxt not in _LAT_VOWELS)
                    or (i > 0 and ch not in _LAT_VOWELS and nxt in _LAT_VOWELS)):
                edits.append((i + 1, i + 1, TUTUQ))
        return edits

    @staticmethod
    def _cyr_edits(word: str) -> list[tuple[int, int, str]]:
        edits = []
        n = len(word)
        for i, ch in enumerate(word):
            if ch in _CYR_SWAP:
                edits.append((i, i + 1, _CYR_SWAP[ch]))
            nxt = word[i + 1] if i + 1 < n else ""
            if nxt and nxt.isalpha() and nxt != "ъ" and (
                    (ch in _CYR_VOWELS and nxt not in _CYR_VOWELS)
                    or (i > 0 and ch not in _CYR_VOWELS and nxt in _CYR_VOWELS)):
                edits.append((i + 1, i + 1, "ъ"))
        return edits

    @staticmethod
    def _apply(word: str, combo) -> str:
        out, last = [], 0
        for a, b, rep in combo:
            out.append(word[last:a])
            out.append(rep)
            last = b
        out.append(word[last:])
        return "".join(out)

    def suggest(self, word: str, script: str) -> str | None:
        """Kichik harfli so'z uchun aniq tuzatish yoki None (natija keshlanadi)."""
        key = (word, script)
        if key in self._suggest_cache:
            return self._suggest_cache[key]
        result = self._suggest(word, script)
        if len(self._suggest_cache) < 500_000:
            self._suggest_cache[key] = result
        return result

    def _suggest(self, word: str, script: str) -> str | None:
        words = self.words(script)
        if not words or len(word) < 3:
            return None
        if script == "lat" and not _NEW_LETTERS.isdisjoint(word):
            return None   # yangi alifbodagi so'z — lug'at eski alifboda
        own = words.get(word, 0)
        need = max(_MIN_FREQ, own * _TYPO_RATIO) if own else _MIN_FREQ
        if own >= 1000:
            return None   # keng tarqalgan so'z — xato emas
        edits = self._lat_edits(word) if script == "lat" else self._cyr_edits(word)
        if not edits or len(edits) > _MAX_POSITIONS * 2:
            return None
        max_k = 2 if script == "lat" else 4
        if len(edits) > _MAX_POSITIONS:
            max_k = min(max_k, 2)
        found: dict[str, int] = {}
        for k in range(1, max_k + 1):
            for combo in itertools.combinations(edits, k):
                if any(combo[j][0] < combo[j - 1][1] or combo[j][0] == combo[j - 1][0]
                       for j in range(1, k)):
                    continue   # bir joyni ikki marta o'zgartirish
                cand = self._apply(word, combo)
                freq = words.get(cand, 0)
                if freq >= need:
                    found[cand] = freq
        if not found:
            return None
        best = sorted(((f, c) for c, f in found.items()), reverse=True)
        if len(best) > 1 and best[0][0] < _RATIO * best[1][0]:
            return None   # ikki xil ma'noli — tegilmaydi
        return best[0][1]


_lexicon: Lexicon | None = None
_ready = False


def get_lexicon() -> Lexicon | None:
    """Lug'at (fayllar bo'lmasa None — qoidalar lug'atsiz ishlaydi)."""
    global _lexicon, _ready
    if not _ready:
        paths = {s: os.path.join(_DIR, f) for s, f in _FILES.items()
                 if os.path.exists(os.path.join(_DIR, f))}
        _lexicon = Lexicon(paths) if paths else None
        _ready = True
    return _lexicon
