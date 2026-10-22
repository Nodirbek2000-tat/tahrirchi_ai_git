"""Kirill matn o'zbekchami yoki ruschami — tez aniqlash (AI'siz).

Har bir paragraf alohida baholanadi. Har bir so'z dalil beradi:
  o'zbek — ў қ ғ ҳ harflari (rusda yo'q), yordamchi so'zlar (ва, учун, билан ...),
           qo'shimchalar (-нинг, -ларни, -лиги, -илмий ...). Maxsus harflarsiz
           (у/к/г/х bilan) yozilgan o'zbekcha matn ham qo'shimchalaridan taniladi.
  rus    — ы щ ь harflari, yordamchi so'zlar (и, в, на, что ...),
           qo'shimchalar (-ться, -ого, -ость, -ство ...).
Natija: "uz", "ru" yoki None (qisqa/aniqlab bo'lmaydigan matn — masalan, "Бухоро").
None bo'lgan paragraflar hujjatdagi ko'pchilik tiliga qarab hal qilinadi.
"""

import re
from functools import lru_cache

_UZ_LETTERS = frozenset("ўқғҳ")
_RU_LETTERS = frozenset("ыщ")
_WORD_RE = re.compile(r"[а-яёўқғҳъь]+")
_RU_AFTER_HARD = frozenset("еёюя")

_RU_WORDS = frozenset((
    "и в во на не ни что чтобы с со по это как для от из к ко о об обо за но а же бы то "
    "все всё всех всего всем так его её ее их им ему ей них ним ней нём нем он она оно они "
    "мы вы я ты меня мне тебя тебе себя себе нас нам вас вам был была было были будет "
    "будут есть или при до после также тоже который которая которое которые которых "
    "которым котором этот эта эти этого этой этим этом тот та те того той тем том чем "
    "где когда только уже может могут нет более менее между через под над без ещё еще "
    "очень можно нужно надо если свой своя своё свое свои своей своих свою наш наша наше "
    "наши мой моя мое моё мои ваш ваша ваши кто почему зачем сам сама само сами один одна "
    "одно два три много мало лишь даже ведь вот однако кроме среди вместе около против "
    "согласно благодаря поэтому потому является являются году года лет данный данной "
    "данных рамках целью необходимо должен должна должны "
    # ҳужжат сарлавҳалари
    "введение заключение глава список литература выводы содержание оглавление приложение "
    "актуальность цель задачи объект предмет новизна таблица рисунок рис табл стр г гг"
).split())

_UZ_WORDS = frozenset((
    "ва бу учун билан ҳам хам эди эса деб бир ёки лекин аммо шу ушбу мазкур барча ҳар хар "
    "бўлган булган бўлиб булиб бўйича буйича орқали оркали каби сўнг сунг кейин ҳақида "
    "хакида ўз уз улар биз сиз мен сен шунингдек яъни эмас бор йўқ йук керак ҳамда хамда "
    "жуда янги катта кўп куп ҳозир хозир ҳозирги хозирги асосий бошқа бошка энг агар чунки "
    "балки ҳатто хатто ўша уша нима ким қандай кандай қачон качон йил йили йилда йилги "
    "илмий миллий тарихий амалий назарий кўра кура тўғрисида тугрисида шаҳар шахар шаҳри "
    "шахри вилояти тумани ташкил этиш этади этилган қилиш килиш қилди килди қилган килган "
    "олиб келиб бориб ҳисобланади хисобланади аср асрда бугун бугунги кун куни "
    "икки уч тўрт турт беш олти етти саккиз тўққиз туккиз ўн юз минг буюк дарс мавзу "
    # ҳужжат сарлавҳалари
    "кириш хулоса боб мундарижа адабиётлар илова"
).split())

# Kuchli qo'shimchalar (+2) — boshqa tilda deyarli uchramaydi; kuchsizlari (+1)
_RU_STRONG = (
    "тся", "ться", "ство", "ства", "ству", "ством", "стве", "ского", "ской", "ские", "ских",
    "ское", "ская", "ость", "ости", "остью",
    # -ния: faqat rusga xos shakllar (o'zbekda ham bor: компания, Германия)
    "вания", "ления", "шения", "жения", "чения", "рения", "дения", "нения", "сения", "зания",
)
_RU_WEAK = (
    "ого", "его", "ает", "яет", "ует", "ают", "яют", "уют", "ный", "ная", "ное", "ные",
    "ных", "ными", "ную", "ным", "ном", "ной", "ыми", "ский", "кий", "ая", "ое", "ую", "юю",
    "ами", "ями", "ние", "нию", "нием", "нии", "тие", "тия",
)
_UZ_STRONG = (
    "нинг", "ларни", "ларга", "лардан", "ларда", "лари", "моқда", "мокда", "лигини",
    "лигида", "ликдан", "ганлар", "ганини", "адилар", "дилар", "мизда", "мизни", "мизга",
    "миздан", "нгизда", "нгизни", "нгизга",
)
_UZ_WEAK = (
    "лар", "даги", "ишни", "ишга", "ишда", "ишдан", "лиги", "ликни", "ликда", "ликка",
    "миз", "ингиз", "лган", "нган", "тган", "дган", "шган", "ганда", "гандан", "гани",
    "ади", "сида", "сини", "сига", "ини", "тдан", "ндан", "лдан", "мий", "бий", "вий",
    "оий", "сий", "нги", "рги", "нга", "рида", "чида", "тида", "сга", "тга", "тда", "кда",
    "шда", "шга",
)
_MIN_SCORE = 2   # qaror uchun kamida shuncha dalil (bitta qo'shimchaning o'zi yetmaydi)


@lru_cache(maxsize=8192)
def classify_cyrillic(text: str) -> str | None:
    uz = ru = 0
    for w in _WORD_RE.findall(text.lower()):
        if w in _RU_WORDS:
            ru += 2
            continue
        if w in _UZ_WORDS:
            uz += 2
            continue
        has_uz = not _UZ_LETTERS.isdisjoint(w)
        if has_uz:
            uz += 2
        if not _RU_LETTERS.isdisjoint(w):
            ru += 2
        if "ь" in w:
            ru += 1
        hard = w.find("ъ")
        if hard >= 0:
            # Rusda: подъезд (ъ + е/ё/ю/я); o'zbekda tutuq: маъно, таълим
            if hard + 1 < len(w) and w[hard + 1] in _RU_AFTER_HARD:
                ru += 1
            else:
                uz += 1
        if len(w) > 4 and not has_uz:
            if w.endswith(_RU_STRONG):
                ru += 2
            elif w.endswith(_UZ_STRONG):
                uz += 2
            elif w.endswith(_RU_WEAK):
                ru += 1
            elif w.endswith(_UZ_WEAK):
                uz += 1
    if uz > ru and uz >= _MIN_SCORE:
        return "uz"
    if ru > uz and ru >= _MIN_SCORE:
        return "ru"
    return None


_NEIGHBORS = 8
_CYR_RE = re.compile("[Ѐ-ӿ]")


def neighbor_contexts(texts: list[str]) -> list[str | None]:
    """Tili aniqlanmagan paragraf uchun eng yaqin aniqlangan qo'shni paragraf matni.

    Bo'limlar odatda bir tilda bo'ladi: rus bo'limidagi "Таблица 2", "Город" kabi
    sarlavha va kataklar rus qo'shnisiga, o'zbek bo'limidagisi o'zbek qo'shnisiga
    qarab hal qilinadi. Masofa faqat kirill matnli paragraflar bo'yicha sanaladi
    (jadvaldagi raqamli kataklar hisobga kirmaydi). Teng masofada keyingi paragraf
    afzal (sarlavha o'zidan keyingi bo'limga tegishli).
    Natija: har bir matn uchun kontekst yoki None (o'zi aniqlangan / qo'shni topilmadi).
    """
    out: list[str | None] = [None] * len(texts)
    cyr = [i for i, t in enumerate(texts) if t and _CYR_RE.search(t)]
    langs = [classify_cyrillic(texts[i]) for i in cyr]
    n = len(cyr)
    for k, lang in enumerate(langs):
        if lang is not None:
            continue
        for d in range(1, _NEIGHBORS + 1):
            if k + d < n and langs[k + d]:
                out[cyr[k]] = texts[cyr[k + d]]
                break
            if k - d >= 0 and langs[k - d]:
                out[cyr[k]] = texts[cyr[k - d]]
                break
    return out


# ============================================================ Lotin: o'zbekcha yoki inglizcha
_LAT_WORD_RE = re.compile(r"[a-z']+")
_APOS_TO_PLAIN = str.maketrans({c: "'" for c in "ʻʼ‘’`´ʹ′ˈ‛ʽꞌ"})
_UZL_WORDS = frozenset((
    "va bu uchun bilan ham edi esa deb bir yoki lekin ammo shu ushbu mazkur barcha har "
    "bo'lgan bo'lib bo'yicha orqali kabi keyin haqida o'z ular biz siz men sen shuningdek "
    "ya'ni emas bor yo'q kerak hamda juda yangi katta ko'p hozir hozirgi asosiy boshqa eng "
    "agar chunki balki hatto o'sha nima kim qanday qachon yil yili yilda ilmiy milliy "
    "tarixiy ko'ra to'g'risida shahar shahri viloyati tumani tashkil etish etadi qilish "
    "qildi qilgan olib kelib bugun kun ikki uch to'rt besh o'n yuz ming qism bob kirish "
    "xulosa mundarija ishi ish deyarli faqat hamma butun"
).split())
_EN_WORDS = frozenset((
    "the and of to in is are was were for with that this on as by from at an be it or not "
    "have has had which their they you we he she but been will would can could there what "
    "about into than its also more these other some such only most may after over all one "
    "two new our your his her them who when where how why if so no do does did use used"
).split())
_UZL_ENDINGS = ("lar", "larni", "larga", "larda", "lardan", "lari", "ning", "dagi", "moqda",
                "ligi", "lik", "ganlar", "gan", "adi", "ilar", "ishi", "ini", "iga", "ida",
                "idan", "lari", "miz", "ingiz", "chi", "siz")
_EN_ENDINGS = ("tion", "tions", "ing", "ness", "ment", "ments", "ous", "ity", "ies", "ed",
               "ly", "able", "ible", "ful", "less", "ship", "ive")


@lru_cache(maxsize=8192)
def classify_latin(text: str) -> str | None:
    """Lotin matn o'zbekchami ("uz") yoki inglizchami ("en"); aniqlanmasa None."""
    low = text.lower().translate(_APOS_TO_PLAIN)
    uz = en = 0
    for w in _LAT_WORD_RE.findall(low):
        w = w.strip("'")
        if not w:
            continue
        if w in _UZL_WORDS:
            uz += 2
            continue
        if w in _EN_WORDS:
            en += 2
            continue
        if "o'" in w or "g'" in w or "q" in w and "qu" not in w:
            uz += 2
        elif "w" in w or "th" in w or re.search(r"c(?!h)", w):
            en += 1
        if len(w) > 4:
            if w.endswith(_UZL_ENDINGS):
                uz += 1
            elif w.endswith(_EN_ENDINGS):
                en += 1
    if uz > en and uz >= _MIN_SCORE:
        return "uz"
    if en > uz and en >= _MIN_SCORE:
        return "en"
    return None


def script_of(text: str) -> str | None:
    """Matnning asosiy yozuvi: "cyr", "lat" yoki None (harf yo'q)."""
    cyr = lat = 0
    for ch in text:
        if "Ѐ" <= ch <= "ӿ":
            cyr += 1
        elif ch.isascii() and ch.isalpha() or ch in "şçğöŞÇĞÖ":
            lat += 1
    if not cyr and not lat:
        return None
    return "cyr" if cyr >= lat else "lat"


def resolve_languages(texts: list[str], unknown_cyr_is_uz: bool = True) -> list[str | None]:
    """Har bir paragraf tili: "uz_cyr", "ru", "uz_lat", "en" yoki None (harf yo'q).

    Aniqlanmagan qisqa paragraf shu yozuvdagi eng yaqin aniqlangan qo'shnisiga,
    u ham bo'lmasa: kirill — unknown_cyr_is_uz, lotin — o'zbekcha deb olinadi.
    """
    scripts = [script_of(t) if t else None for t in texts]
    langs: list[str | None] = []
    for t, s in zip(texts, scripts):
        if s == "cyr":
            lang = classify_cyrillic(t)
            langs.append({"uz": "uz_cyr", "ru": "ru"}.get(lang) if lang else None)
        elif s == "lat":
            lang = classify_latin(t)
            langs.append({"uz": "uz_lat", "en": "en"}.get(lang) if lang else None)
        else:
            langs.append(None)
    out = list(langs)
    for script, fallback in (("cyr", "uz_cyr" if unknown_cyr_is_uz else "ru"), ("lat", "uz_lat")):
        idx = [i for i, s in enumerate(scripts) if s == script]
        n = len(idx)
        for k, i in enumerate(idx):
            if langs[i] is not None:
                continue
            found = None
            for d in range(1, _NEIGHBORS + 1):
                if k + d < n and langs[idx[k + d]]:
                    found = langs[idx[k + d]]
                    break
                if k - d >= 0 and langs[idx[k - d]]:
                    found = langs[idx[k - d]]
                    break
            out[i] = found or fallback
    return out
