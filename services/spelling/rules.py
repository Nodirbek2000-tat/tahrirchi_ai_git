"""O'zbek imlosi va tinish belgilari — AI'siz qoidalar (lotin va kirill).

fix(text, lang, starts) — paragrafni tuzatilgan holga keltiradi (qayta qo'llansa
o'zgarmaydi). Faqat ANIQ xatolar tuzatiladi; shubhali joylarga tegilmaydi.

Qoidalar tartibi:
  1. aralash harflar — kirill so'z ichidagi lotin "о/а/е" (va aksincha)
  2. tutuq/oʻ, gʻ — o' o` o’ -> oʻ, g' -> gʻ, ma'no -> maʼno (kirillda -> ъ)
  3. so'zlar — lug'at bo'yicha klaviatura xatolari (Узбекистон -> Ўзбекистон, xozir -> hozir)
  4. qo'shtirnoq — "..." -> «...» yoki “...”
  5. tire — "so'z - so'z" -> "so'z — so'z"
  6. bo'sh joylar — "salom ,dunyo" -> "salom, dunyo", "( matn )" -> "(matn)"
  7. vergul — "lekin/ammo/biroq/chunki" oldidan, kirish so'zlardan keyin, "Agar ...-sa," dan keyin
  8. katta harf — gap boshi, atoqli otlar (Toshkent, Oʻzbekiston ...)
"""

import re

from services.converters import LatToCyrConverter
from services.transliteration import APOSTROPHES, protected_spans

OKINA = "ʻ"   # oʻ, gʻ
TUTUQ = "ʼ"   # maʼno

_L = r"[^\W\d_]"   # istalgan harf
_CYR_UP = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯЎҚҒҲ"
_CYR_LOW = _CYR_UP.lower()
_CYR_ALL = _CYR_UP + _CYR_LOW

# ---------------------------------------------------------------- 1. aralash harflar
_LAT2CYR = dict(zip("aceopxyABCEHKMOPTXY", "асеорхуАВСЕНКМОРТХУ"))
_CYR2LAT = {v: k for k, v in _LAT2CYR.items()}
_TOKEN_RE = re.compile(rf"{_L}+")


def _homoglyphs(text: str) -> str:
    def repl(m):
        word = m.group(0)
        cyr = sum(1 for c in word if c in _CYR_ALL)
        lat = sum(1 for c in word if c.isascii())
        if not cyr or not lat or cyr == lat:
            return word
        table = _LAT2CYR if cyr > lat else _CYR2LAT
        minority = [c for c in word if (c.isascii() if cyr > lat else c in _CYR_ALL)]
        if not all(c in table for c in minority):
            return word   # o'xshash bo'lmagan harf — ataylab yozilgan (masalan, kod)
        return "".join(table.get(c, c) for c in word)
    return _TOKEN_RE.sub(repl, text)


# ---------------------------------------------------------------- 2. tutuq va oʻ/gʻ
_APOS_CLASS = "[" + re.escape(APOSTROPHES) + "]"
_NOT_OKINA = "[" + re.escape(APOSTROPHES.replace(OKINA, "")) + "]"
_NOT_TUTUQ = "[" + re.escape(APOSTROPHES.replace(TUTUQ, "")) + "]"
_OG_RE = re.compile(rf"(?<=[gG]){_NOT_OKINA}|(?<=[oO]){_NOT_OKINA}(?={_L})")
_TUTUQ_RE = re.compile(rf"(?<=[^\W\d_oOgG]){_NOT_TUTUQ}(?={_L})")
_CYR_APOS_RE = re.compile(rf"(?<=[{_CYR_ALL}]){_APOS_CLASS}(?=[{_CYR_ALL}])")


def _apostrophes(text: str, lang: str) -> str:
    if lang == "uz_lat":
        text = _OG_RE.sub(OKINA, text)
        return _TUTUQ_RE.sub(TUTUQ, text)

    def cyr(m):
        prev = text[m.start() - 1]
        return "Ъ" if prev.isupper() and text[m.end()].isupper() else "ъ"
    return _CYR_APOS_RE.sub(cyr, text)


# ---------------------------------------------------------------- 3. so'zlar (lug'at)
_LAT_WORD_RE = re.compile(rf"{_L}+(?:[{OKINA}{TUTUQ}]{_L}+)*[{OKINA}]?")


def _words(text: str, lang: str, lexicon) -> str:
    if lexicon is None:
        return text
    script = "lat" if lang == "uz_lat" else "cyr"
    rx = _LAT_WORD_RE if script == "lat" else _TOKEN_RE

    def repl(m):
        word = m.group(0)
        if len(word) < 3 or word.isupper() or any(c.isupper() for c in word[1:]):
            return word
        fixed = lexicon.suggest(word.lower(), script)
        if not fixed:
            return word
        return fixed[0].upper() + fixed[1:] if word[0].isupper() else fixed
    return rx.sub(repl, text)


# ---------------------------------------------------------------- 4. qo'shtirnoq
_QUOTE_OPENERS = set(" \t ([{«“„—–-/")


def _quotes(text: str, pair: str) -> str:
    positions = [i for i, c in enumerate(text) if c == '"']
    if not positions or len(positions) % 2:
        return text
    chars = list(text)
    for k, i in enumerate(positions):
        opening = i == 0 or text[i - 1] in _QUOTE_OPENERS
        if opening != (k % 2 == 0):
            return text   # ochilish/yopilish tartibi aniq emas — tegilmaydi
        chars[i] = pair[0] if opening else pair[1]
    return "".join(chars)


# ---------------------------------------------------------------- 5. tire
_DASH_RE = re.compile(r"(?<=\S) (?:-|--) (?=\S)")


def _dashes(text: str, dash: str) -> str:
    def repl(m):
        if text[m.end()].isdigit():
            return m.group(0)   # 5 - 3, 2010 - 2015, harorat - 5 (minus)
        return f" {dash} "
    return _DASH_RE.sub(repl, text)


# ---------------------------------------------------------------- 6. bo'sh joylar
# Yopuvchi qo'shtirnoqdan keyin harf kelsa — u aslida ochuvchi (noto'g'ri yo'nalgan), tegilmaydi
_SPACE_BEFORE_RE = re.compile(
    rf"(?<=\S)[  ]+(?=[,;:!?)\]]|[»”](?!{_L})|\.(?:\s|$|[»”)\]]))"
)
_SPACE_AFTER_OPEN_RE = re.compile(r"(?<=[(\[«“])[  ]+(?=\S)")
_MISSING_SPACE_RE = re.compile(rf"(?<=[^\s\d,;:!?.])([,;:!?])(?={_L})")
_MISSING_SPACE_DOT_RE = re.compile(rf"(?<={_L}{{2}})\.(?=[{_CYR_UP}A-ZŞÇĞÖ]{_L})")
# "yaxshi .Biz" yoki "emas .keyingi" — gap oxiri; ".docx", ".uz" kabi kengaytmalar emas
_SPACE_DOT_WORD_RE = re.compile(rf"(?<={_L})[  ]+\.(?=({_L}+))")
_EXTENSIONS = frozenset(
    "docx doc pdf txt xlsx xls pptx ppt rtf odt csv json xml html htm uz com ru org net "
    "info edu gov exe apk jpg jpeg png gif bmp svg zip rar mp3 mp4 avi mkv py js".split()
)


def _space_dot(m) -> str:
    word = m.group(1)
    if len(word) >= 2 and word.lower() not in _EXTENSIONS and not word.isupper():
        return ". "
    return m.group(0)
_DOUBLE_SPACE_RE = re.compile(r"(?<=\S)  (?=\S)")
_DOUBLE_PUNCT_RE = re.compile(r",,+|;;+|(?<!\.)\.\.(?!\.)")


def _spacing(text: str) -> str:
    def before(m):
        nxt = text[m.end()]
        if nxt == ":" and text[m.start() - 1].isdigit() and text[m.end() + 1:m.end() + 2].isdigit():
            return m.group(0)   # 3 : 1
        return ""
    text = _SPACE_BEFORE_RE.sub(before, text)
    text = _SPACE_DOT_WORD_RE.sub(_space_dot, text)   # "yaxshi .Biz" -> "yaxshi. Biz"
    text = _SPACE_AFTER_OPEN_RE.sub("", text)
    text = _MISSING_SPACE_RE.sub(r"\1 ", text)
    text = _MISSING_SPACE_DOT_RE.sub(". ", text)
    text = _DOUBLE_SPACE_RE.sub(" ", text)
    return _DOUBLE_PUNCT_RE.sub(lambda m: m.group(0)[0], text)


# ---------------------------------------------------------------- 7. vergul
_CONJ_LAT = ("ammo", "lekin", "biroq", "chunki")
_INTRO_LAT = (
    "albatta", "afsuski", "shubhasiz", "menimcha", "sizningcha", "mening fikrimcha",
    "birinchidan", "ikkinchidan", "uchinchidan", "toʻrtinchidan", "beshinchidan",
    "demak", "xullas", "masalan", "aksincha", "aytgancha", "darvoqe", "qisqasi",
    "aftidan", "xususan", "binobarin", "shunday qilib", "bundan tashqari",
    "umuman olganda", "boshqacha aytganda", "shu bilan birga", "bir tomondan",
    "ikkinchi tomondan", "haqiqatan ham",
)
_COND_LAT = ("sa", "sam", "sang", "sangiz", "sak", "salar", "sangizlar")
_L2C = LatToCyrConverter()
_CONJ_CYR = tuple(_L2C.convert(w) for w in _CONJ_LAT)
_INTRO_CYR = tuple(_L2C.convert(w) for w in _INTRO_LAT)
_COND_CYR = tuple(_L2C.convert(w) for w in _COND_LAT)


def _alt(words) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


# -sa bilan tugaydigan, lekin shart fe'li bo'lmagan so'zlar
_NOT_COND_LAT = ("esa", "kassa", "musa", "isa", "pyesa", "nasa", "prosa", "masa", "hatto")
_NOT_COND_CYR = ("эса", "касса", "муса", "иса", "пьеса", "проза", "маса")


def _comma_res(conj, intro, cond, agar):
    return (
        re.compile(rf"(?<=[^\W_»”)])( )(?=(?:{_alt(conj)})(?!{_L}))", re.IGNORECASE),
        re.compile(rf"(^|[.!?]\s+)((?:{_alt(intro)}))(?= {_L})", re.IGNORECASE),
        re.compile(rf"(^|[.!?]\s+)({agar}(?: {_L}+)*?)(?= {_L})", re.IGNORECASE),
        tuple(cond),
    )


_COMMA = {
    "uz_lat": (_comma_res(_CONJ_LAT, _INTRO_LAT, _COND_LAT, "agar"), "va", "ham", _NOT_COND_LAT),
    "uz_cyr": (_comma_res(_CONJ_CYR, _INTRO_CYR, _COND_CYR, "агар"), "ва", "ҳам", _NOT_COND_CYR),
}


_WORD_ONLY_RE = re.compile(rf"{_L}+")
_PREV_WORD_RE = re.compile(rf"({_L}+)\W*$")
_SENT_STOP_RE = re.compile(r"[.!?]")


def _cond_comma(text: str, m, cond: tuple, ham: str, not_cond: tuple) -> int | None:
    """"Agar ... kelsa biz ..." -> "Agar ... kelsa, biz ...": birinchi shart fe'lidan
    keyin vergul qo'yiladigan o'rin (yoki None)."""
    start = m.end(1)
    stop = _SENT_STOP_RE.search(text, start)
    words = list(_WORD_ONLY_RE.finditer(text, start, stop.start() if stop else len(text)))
    for k, w in enumerate(words[1:], start=1):
        token = w.group(0).lower()
        end = w.end()
        if end >= len(text) or text[end] != " ":
            return None   # vergul/nuqta bor yoki gap tugadi
        if token.endswith(cond) and token not in not_cond and len(token) >= 4:
            nxt = words[k + 1].group(0).lower() if k + 1 < len(words) else ""
            if not nxt or nxt == ham:
                return None   # "kelsa ham" — AI hal qiladi
            return end
    return None


def _commas(text: str, lang: str) -> str:
    (conj_re, intro_re, agar_re, cond), va, ham, not_cond = _COMMA[lang]

    def conj(m):
        prev_word = _PREV_WORD_RE.search(text[max(0, m.start() - 30):m.start()])
        if prev_word and prev_word.group(1).lower() == va:
            return m.group(0)   # "va lekin"
        return ", "
    text = conj_re.sub(conj, text)
    text = intro_re.sub(lambda m: m.group(1) + m.group(2) + ",", text)

    cuts = [p for m in agar_re.finditer(text)
            if (p := _cond_comma(text, m, cond, ham, not_cond)) is not None]
    for p in reversed(cuts):
        text = text[:p] + "," + text[p:]
    return text


# ---------------------------------------------------------------- 8. katta harf
# Qisqartmalar — nuqtadan keyin gap tugamaydi (t.b., h.k., va b.)
_ABBR = frozenset((
    "t.b", "h.k", "va b", "sh.k", "m", "y", "yy", "mil", "av", "r", "jad", "s", "t", "b",
    "prof", "dots", "akad", "f.-m.f.d", "i.f.n", "i.f.d", "t.f.n", "t.f.d", "f.f.n", "p.f.n",
    "tex", "ingl", "rus", "lot", "qad", "q", "sh", "vil", "tum", "koʻch", "ming", "mln",
    "mlrd", "so'm", "soʻm", "kg", "km", "sm", "mm", "gr", "ga", "dr", "str", "bet", "nashr",
    "shahr", "tah", "muh", "res", "resp", "bosh", "red", "tuz", "him", "fan", "dok",
    "т.б", "ҳ.к", "ва б", "ш.к", "м", "й", "йй", "мил", "ав", "р", "жад", "с", "т", "б",
    "проф", "доц", "акад", "тех", "ингл", "рус", "лот", "қад", "қ", "ш", "вил", "тум",
    "кўч", "минг", "млн", "млрд", "сўм", "кг", "км", "см", "мм", "гр", "га", "бет", "наш",
))
_SENT_END_RE = re.compile(rf"([.!?])(\s+)(?=[«“\"(]?{_L})")
_LIST_MARKER_RE = re.compile(rf"^\s*{_L}\)")
_FIRST_LETTER_RE = re.compile(rf"^[\s«“\"'(\[—–\-•·*]*(?:\d+\.\s+)?({_L}{_L}*)")
_CAP_SKIP = frozenset(("km", "kg", "sm", "mm", "ml", "mg", "gr", "sh", "va", "ва"))

# Atoqli otlar (kichik harf bilan yozilgan bo'lsa katta qilinadi). Oddiy so'zga o'xshash
# nomlar (Qarshi — "qarshi", Guliston, Furqat, Fitrat ...) ataylab kiritilmagan.
_PROPER_LAT = (
    "Oʻzbekiston", "Toshkent", "Samarqand", "Buxoro", "Xiva", "Namangan", "Andijon",
    "Fargʻona", "Qashqadaryo", "Surxondaryo", "Navoiy", "Jizzax", "Sirdaryo", "Xorazm",
    "Qoraqalpogʻiston", "Nukus", "Termiz", "Urganch", "Margʻilon", "Qoʻqon", "Chirchiq",
    "Angren", "Bekobod", "Shahrisabz", "Kattaqoʻrgʻon", "Yangiyoʻl", "Denov",
    "Rossiya", "Qozogʻiston", "Qirgʻiziston", "Tojikiston", "Turkmaniston", "Afgʻoniston",
    "Turkiya", "Yaponiya", "Koreya", "Germaniya", "Fransiya", "Angliya",
    "Britaniya", "Italiya", "Ispaniya", "Amerika", "Hindiston", "Pokiston", "Eron", "Iroq",
    "Misr", "Ukraina", "Belarus", "Polsha", "Kanada", "Avstraliya", "Braziliya", "Moskva",
    "London", "Parij", "Istanbul", "Ankara", "Dushanbe", "Bishkek", "Olmaota",
    "Temur", "Ulugʻbek", "Beruniy", "Xorazmiy", "Farobiy", "Buxoriy", "Termiziy",
    "Qodiriy", "Muqimiy", "Ogahiy", "Uvaysiy", "Yassaviy", "Alisher", "Zahiriddin",
)
# Kirillda davlat nomlari rus imlosida yoziladi (Франция, Германия) — alohida ro'yxat
_PROPER_CYR = (
    "Ўзбекистон", "Тошкент", "Самарқанд", "Бухоро", "Хива", "Наманган", "Андижон",
    "Фарғона", "Қашқадарё", "Сурхондарё", "Навоий", "Жиззах", "Сирдарё", "Хоразм",
    "Қорақалпоғистон", "Нукус", "Термиз", "Урганч", "Марғилон", "Қўқон", "Чирчиқ",
    "Ангрен", "Бекобод", "Шаҳрисабз", "Каттақўрғон", "Янгийўл", "Денов",
    "Россия", "Қозоғистон", "Қирғизистон", "Тожикистон", "Туркманистон", "Афғонистон",
    "Туркия", "Япония", "Корея", "Германия", "Франция", "Англия", "Британия", "Италия",
    "Испания", "Америка", "Ҳиндистон", "Покистон", "Эрон", "Ироқ", "Миср", "Украина",
    "Беларус", "Польша", "Канада", "Австралия", "Бразилия", "Москва", "Лондон", "Париж",
    "Истанбул", "Анқара", "Душанбе", "Бишкек", "Олмаота",
    "Темур", "Улуғбек", "Беруний", "Хоразмий", "Форобий", "Бухорий", "Термизий",
    "Қодирий", "Муқимий", "Огаҳий", "Увайсий", "Яссавий", "Алишер", "Заҳириддин",
)
_CASE_SUFFIX = ("", "ning", "ni", "ga", "ka", "qa", "da", "dan", "dagi", "gacha")
_CASE_SUFFIX_CYR = ("", "нинг", "ни", "га", "ка", "қа", "да", "дан", "даги", "гача")


def _proper_map(names, suffixes) -> dict:
    out = {}
    for name in names:
        for suf in suffixes:
            out[(name + suf).lower()] = name + suf
    return out


_PROPER = {"uz_lat": _proper_map(_PROPER_LAT, _CASE_SUFFIX),
           "uz_cyr": _proper_map(_PROPER_CYR, _CASE_SUFFIX_CYR)}


def _capitalizable(word: str) -> bool:
    return (word.islower() and word.lower() not in _CAP_SKIP
            and (len(word) > 1 or word in "uуo"))


_TOKEN_BEFORE_RE = re.compile(rf"((?:{_L}+[.-])*{_L}+|\d+)$")


def _token_before(text: str, end: int) -> str:
    """Nuqtadan oldingi so'z (nuqtali qisqartma bilan): "t.b" , "Toshkent"."""
    m = _TOKEN_BEFORE_RE.search(text[max(0, end - 40):end])
    return m.group(1) if m else ""


def _capitals(text: str, lang: str, starts: bool) -> str:
    chars = list(text)

    if starts and not _LIST_MARKER_RE.match(text):
        m = _FIRST_LETTER_RE.match(text)
        if m and _capitalizable(m.group(1)):
            chars[m.start(1)] = text[m.start(1)].upper()

    for m in _SENT_END_RE.finditer(text):
        punct = m.group(1)
        if punct == ".":
            if text[max(0, m.start() - 2):m.start()] == "..":
                continue   # ko'p nuqta — gap davom etadi
            token = _token_before(text, m.start())
            if not token or token[-1].isdigit() or token.lower() in _ABBR or len(token) <= 2:
                continue
        start = m.end()
        while start < len(text) and not text[start].isalpha():
            start += 1
        word = _TOKEN_RE.match(text, start)
        if word and _capitalizable(word.group(0)):
            chars[start] = text[start].upper()

    proper = _PROPER[lang]
    out = "".join(chars)
    rx = _LAT_WORD_RE if lang == "uz_lat" else _TOKEN_RE
    return rx.sub(lambda m: proper.get(m.group(0), m.group(0)) if m.group(0).islower()
                  else m.group(0), out)


# ---------------------------------------------------------------- yig'ma
def _protected(fn):
    """URL/email ichiga tegmaslik: ular vaqtincha belgilarga almashtiriladi."""
    def wrapper(text: str, *args) -> str:
        spans = protected_spans(text)
        if not spans:
            return fn(text, *args)
        keep = {}
        parts, last = [], 0
        for k, (a, b) in enumerate(spans):
            key = chr(0xE000 + k)
            keep[key] = text[a:b]
            parts.append(text[last:a])
            parts.append(key)
            last = b
        parts.append(text[last:])
        out = fn("".join(parts), *args)
        for key, value in keep.items():
            out = out.replace(key, value)
        return out
    return wrapper


@_protected
def _one_pass(text: str, lang: str, starts: bool, cells: bool, lexicon, quotes: str,
              dash: str) -> str:
    text = _homoglyphs(text)
    text = _apostrophes(text, lang)
    text = _words(text, lang, lexicon)
    if cells:
        return text
    text = _quotes(text, quotes)
    text = _dashes(text, dash)
    text = _spacing(text)
    text = _commas(text, lang)
    return _capitals(text, lang, starts)


def default_quotes(lang: str) -> str:
    return "«»" if lang == "uz_cyr" else "“”"


def fix(text: str, lang: str, starts: bool = True, cells: bool = False, lexicon=None,
        quotes: str | None = None, dash: str = "—") -> str:
    """Paragrafni tuzatadi. lang: "uz_lat" | "uz_cyr". Natija — qo'zg'almas nuqta."""
    if not text or not any(c.isalpha() for c in text):
        return text
    quotes = quotes or default_quotes(lang)
    for _ in range(4):
        new = _one_pass(text, lang, starts, cells, lexicon, quotes, dash)
        if new == text:
            break
        text = new
    return text


# ---------------------------------------------------------------- gaplarga bo'lish
_SPLIT_RE = re.compile(r"[.!?…]+[»”\")\]]*(?=\s+|$)")


def split_sentences(text: str) -> list[tuple[int, int]]:
    """Gaplar chegaralari (boshlanish, tugash) — qisqartmalar hisobga olinadi."""
    spans, start = [], 0
    for m in _SPLIT_RE.finditer(text):
        if m.group(0)[0] == "." and len(m.group(0).rstrip("»”\")]")) == 1:
            token = _token_before(text, m.start())
            if token.lower() in _ABBR or (len(token) <= 2 and not token.isdigit()):
                continue
        end = m.end()
        a, b = start, end
        while a < b and text[a].isspace():
            a += 1
        if a < b:
            spans.append((a, b))
        start = end
    a, b = start, len(text)
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    if a < b:
        spans.append((a, b))
    return spans


def ends_sentence(text: str | None) -> bool:
    """Oldingi paragraf/qator gapni tugatganmi (keyingisi katta harf bilan boshlanadi)."""
    if text is None:
        return True
    t = text.rstrip().rstrip("»”\")]")
    return not t or t[-1] in ".!?…"
