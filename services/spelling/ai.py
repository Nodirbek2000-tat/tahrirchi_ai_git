"""AI faqat kerakli joyda: qoidalar hal qila olmagan murakkab gaplar.

1) Tanlash (AI'siz): faqat o'zbekcha, kamida 5 so'zli va SHUBHALI gaplar yuboriladi:
   lug'atda yo'q so'z bor (imlo xatosi bo'lishi mumkin) yoki vergul kerak bo'lishi
   mumkin bo'lgan uzun gap. Xatosiz ko'ringan gaplar yuborilmaydi.
2) AI javobi QAT'IY tekshiriladi: so'zlar soni va tartibi bir xil, har so'zda
   ko'pi bilan 2 harf farq, raqamlar o'zgarmagan, yozuv (kirill/lotin) o'zgarmagan,
   yangi so'z lug'atda bor. Shartga to'g'ri kelmasa — AI tuzatishi tashlanadi.
3) Kesh: bir xil gap qayta-qayta yuborilmaydi (sarlavhalar, kolontitullar).
"""

import logging
import re
from collections import OrderedDict

from data import config
from services.language import script_of
from services.spelling import rules
from services.spelling.converter import SpellConverter, SpellCtx

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[^\W\d_]+")
_DIGITS_RE = re.compile(r"\d+")
_ALLOWED_PUNCT = frozenset(",.;:!?—–-«»“”\"()…")
_COND_RE = re.compile(r"(?:sa|sam|sang|sangiz|sak|salar|са|сам|санг|сангиз|сак|салар)$")
_CLAUSE_RE = re.compile(
    r"(?:gach|ganda|guncha|gani|ganidan|kach|kanda|qach|qanda|гач|ганда|гунча|ганидан|кач|канда|қач|қанда)$"
)

_FOREIGN_RE = re.compile(r"[цщьы]|w|c(?!h)")
# Tuslangan fe'l (keldik, boradi, o'qiyapti, ko'rgan ...): 2 ta va undan ko'p bo'lsa —
# qo'shma gap, ular orasida vergul kerak bo'lishi mumkin
_VERB_RE = re.compile(
    r"(?:dik|dim|ding|dingiz|dilar|ydi|adi|aydi|amiz|aman|asiz|asan|moqda|yapti|yapmiz|"
    r"ishdi|gan|ganmiz|ganman|ganlar|"
    r"дик|дим|динг|дингиз|дилар|йди|ади|айди|амиз|аман|асиз|асан|моқда|япти|япмиз|ишди|"
    r"ган|ганмиз|ганман|ганлар)$"
)

_CACHE: "OrderedDict[str, str | None]" = OrderedDict()
_CACHE_MAX = 50_000


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _score(sentence: str, script: str, lexicon) -> int:
    words = _words(sentence)
    if len(words) < 5 or len(sentence) > 600:
        return 0
    score = 0
    if lexicon is not None:
        unknown = 0
        for i, w in enumerate(words):
            if len(w) < 4 or w.isupper() or (i and w[0].isupper()):
                continue   # qisqa so'z, qisqartma, atoqli ot
            if _FOREIGN_RE.search(w.lower()):
                continue   # rus/ingliz o'zlashma (цирк, компьютер, show)
            if not lexicon.known(w, script):
                unknown += 1
        score += 3 * min(unknown, 2)
    commas = sentence.count(",")
    inner = [w.lower() for w in words[1:-1]]
    if any(_COND_RE.search(w) or _CLAUSE_RE.search(w) for w in inner) and not commas:
        score += 2
    verbs = sum(1 for w in words if len(w) >= 4 and _VERB_RE.search(w.lower()))
    if verbs >= 2 and not commas and len(words) >= 7:
        score += 2
    if len(words) >= 15 and not commas:
        score += 2
    elif len(words) >= 25 and commas <= 1:
        score += 1
    return score


def select(texts_ctx, conv: SpellConverter, limit: int | None = None) -> list[tuple[str, str]]:
    """AI'ga yuboriladigan (gap, til) juftlari — gap qoidalar qo'llangandan keyingi holida."""
    limit = limit or config.SPELL_AI_MAX_SENTENCES
    scored: dict[str, tuple[int, str]] = {}
    for text, ctx in texts_ctx:
        if not isinstance(ctx, SpellCtx) or ctx.lang is None:
            continue
        fixed = conv.rule_fix(text, ctx)
        script = "lat" if ctx.lang == "uz_lat" else "cyr"
        for a, b in rules.split_sentences(fixed):
            sentence = fixed[a:b]
            if sentence in scored:
                continue
            s = _score(sentence, script, conv.lexicon)
            if s >= 2:
                scored[sentence] = (s, ctx.lang)
    ranked = sorted(scored, key=lambda k: -scored[k][0])
    return [(s, scored[s][1]) for s in ranked[:limit]]


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def validate(orig: str, new: str, lang: str, lexicon) -> str | None:
    """AI tuzatgan gap xavfsizmi. Xavfsiz bo'lsa (qoidalar bilan tozalangan) gapni qaytaradi."""
    if not new or new == orig:
        return None
    new = rules.fix(new.strip(), lang, starts=False, lexicon=lexicon)
    if orig[:1].isalpha() and new[:1].isalpha() and orig[0].isupper() != new[0].isupper():
        new = (new[0].upper() if orig[0].isupper() else new[0].lower()) + new[1:]
    if new == orig or script_of(new) != script_of(orig):
        return None
    if _DIGITS_RE.findall(orig) != _DIGITS_RE.findall(new):
        return None
    wo, wn = _words(orig), _words(new)
    if len(wo) != len(wn):
        return None
    script = "lat" if lang == "uz_lat" else "cyr"
    changed = 0
    for a, b in zip(wo, wn):
        if a == b:
            continue
        if a.lower() == b.lower():
            if a[1:] != b[1:]:
                return None   # so'z ichida harf kattaligi o'zgargan
            continue
        changed += 1
        d = _levenshtein(a.lower(), b.lower())
        if changed > 3 or d > 2 or d > max(1, len(a) // 3):
            return None
        if lexicon is not None and not lexicon.known(b, script):
            return None
    # So'z va raqamlardan tashqari faqat tinish belgilari o'zgargan bo'lishi kerak
    strip = lambda s: re.sub(r"[^\W_]|\s", "", s)   # noqa: E731
    if (set(strip(orig)) ^ set(strip(new))) - _ALLOWED_PUNCT:
        return None
    return new


async def ai_fixes(ai, candidates: list[tuple[str, str]], lexicon) -> dict[str, str]:
    """{gap: tuzatilgan gap} — faqat xavfsiz deb topilgan AI tuzatishlari."""
    result: dict[str, str] = {}
    lang_of = dict(candidates)
    todo = []
    for s in lang_of:
        if s in _CACHE:
            _CACHE.move_to_end(s)
            if _CACHE[s] is not None:
                result[s] = _CACHE[s]
        else:
            todo.append(s)
    if todo and config.SPELL_AI:
        try:
            answers = await ai.proofread(todo)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI imlo tekshiruvi ishlamadi: %s", exc)
            answers = {}
        accepted = 0
        for i, s in enumerate(todo):
            fixed = None
            if i in answers:
                fixed = validate(s, answers[i], lang_of.get(s, "uz_lat"), lexicon)
            _CACHE[s] = fixed
            if fixed is not None:
                result[s] = fixed
                accepted += 1
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
        logger.info("AI imlo: %s gap yuborildi, %s ta javob, %s ta qabul qilindi",
                    len(todo), len(answers), accepted)
    return result
