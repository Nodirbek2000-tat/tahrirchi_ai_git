"""O'zbek Vikipediyasi arxividan so'zlar lug'atini yasash (bir martalik, qo'lda ishga tushiriladi).

    python tools/build_lexicon.py uzwiki-latest-pages-articles.xml.bz2

Natija: services/spelling/data/uz_lat.txt.gz va uz_cyr.txt.gz ("so'z\\tchastota").
Arxiv: https://dumps.wikimedia.org/uzwiki/latest/ (CC BY-SA). Lug'atda faqat so'zlar va
ularning chastotasi bor — matnning o'zi saqlanmaydi.
"""

import bz2
import gzip
import os
import re
import sys
import time
from collections import Counter
from xml.etree.ElementTree import iterparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.converters import LatToCyrConverter  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "services", "spelling", "data")
MIN_FREQ = 3          # kamida shuncha uchragan so'z lug'atga kiradi
MAX_WORDS = 600_000   # eng ko'p uchraydiganlari

OKINA, TUTUQ = "ʻ", "ʼ"
_APOS = "ʻʼ‘’'`´ʹ′ˈ‛ʽꞌ"
_OG = re.compile(f"(?<=[og])[{_APOS}]")
_TUTUQ_RE = re.compile(f"(?<=[a-fh-np-z])[{_APOS}](?=[a-z])")   # o/g dan keyingisi — oʻ, gʻ
_ENTITY = re.compile(r"&[a-z]+;|&#\d+;")
_WORD = re.compile(f"[a-z{OKINA}{TUTUQ}]+")

_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_TABLE = re.compile(r"\{\|.*?\|\}", re.S)
_REF = re.compile(r"<ref[^>]*?/>|<ref.*?</ref>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_FILE_LINK = re.compile(r"\[\[(?:Fayl|File|Rasm|Image|Tasvir|Kategoriya|Category|Turkum)"
                        r":[^\]]*\]\]", re.I)
_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_EXT_LINK = re.compile(r"\[https?://\S+\s*([^\]]*)\]|https?://\S+")


def clean(text: str) -> str:
    for _ in range(5):   # ichma-ich shablonlar
        new = _TEMPLATE.sub(" ", text)
        if new == text:
            break
        text = new
    text = _TABLE.sub(" ", text)
    text = _REF.sub(" ", text)
    text = _TAG.sub(" ", text)
    text = _ENTITY.sub(" ", text)
    text = _FILE_LINK.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    return _EXT_LINK.sub(r"\1", text)


def words(text: str):
    low = text.lower()
    low = _OG.sub(OKINA, low)
    low = _TUTUQ_RE.sub(TUTUQ, low)
    for w in _WORD.findall(low):
        w = w.strip(TUTUQ).lstrip(OKINA)
        if 2 <= len(w) <= 30:
            yield w


def main(path: str) -> None:
    started = time.time()
    counter: Counter = Counter()
    pages = 0
    ns_ok = redirect = False
    with bz2.open(path, "rb") as f:
        for _, el in iterparse(f, events=("end",)):
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "ns":
                ns_ok = el.text == "0"
            elif tag == "redirect":
                redirect = True
            elif tag == "text":
                if ns_ok and not redirect and el.text:
                    counter.update(words(clean(el.text)))
                    pages += 1
                    if pages % 20000 == 0:
                        print(f"  {pages} maqola, {len(counter)} so'z, {time.time() - started:.0f}s",
                              flush=True)
            elif tag == "page":
                ns_ok = redirect = False
                el.clear()
    lat = [(w, c) for w, c in counter.most_common(MAX_WORDS) if c >= MIN_FREQ]
    print(f"Maqolalar: {pages}, lotin so'zlar: {len(lat)}")

    l2c = LatToCyrConverter(new_mode=False)
    cyr: Counter = Counter()
    for w, c in lat:
        if not re.search("[cwq]u|w|c(?!h)", w):   # inglizcha so'zlar kirillga o'tkazilmaydi
            cyr[l2c.convert(w)] += c

    os.makedirs(OUT_DIR, exist_ok=True)
    for name, items in (("uz_lat.txt.gz", lat), ("uz_cyr.txt.gz", cyr.most_common())):
        out = os.path.join(OUT_DIR, name)
        with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as g:
            for w, c in items:
                g.write(f"{w}\t{c}\n")
        print(f"{name}: {len(items)} so'z, {os.path.getsize(out) / 1e6:.1f} MB")
    print(f"Tayyor: {time.time() - started:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1])
