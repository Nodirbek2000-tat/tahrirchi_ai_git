"""OpenAI: murakkab gaplarda imlo va tinish belgilarini tekshirish.

Tejamkorlik: qoidalar hal qila olmagan gaplargina yuboriladi, javobda esa FAQAT
o'zgargan gaplar qaytadi ({"3": "tuzatilgan gap"}), xatosiz gaplar umuman qaytmaydi —
chiqish tokenlari minimal. AI javobi services/spelling/ai.py da qat'iy tekshiriladi.

Ishonchlilik: kichik guruhlar, cheklangan parallel so'rovlar (semaphore),
har so'rovga timeout, xatoda qayta urinish. Xato bo'lsa gap o'zgarishsiz qoladi.
"""

import asyncio
import json
import logging

from openai import AsyncOpenAI

from data import config
from db import session_maker
from db.repositories.setting import SettingRepository

logger = logging.getLogger(__name__)

_PROOFREAD_PROMPT = (
    "You are a strict proofreader for UZBEK texts. Input: JSON object, key = id, "
    "value = one Uzbek sentence (Latin or Cyrillic script).\n"
    "Fix ONLY: misspelled words and missing/wrong punctuation (especially commas) "
    "according to official Uzbek orthography and punctuation rules.\n"
    "STRICT RULES:\n"
    "1. Never rephrase, never translate, never change word order, never add or remove words.\n"
    "2. Keep the script: Cyrillic stays Cyrillic, Latin stays Latin. In Latin use "
    "oʻ gʻ with ʻ and the tutuq sign ʼ.\n"
    "3. Do not touch names, numbers, abbreviations, foreign or Russian words.\n"
    "4. If unsure — leave the sentence unchanged.\n"
    "5. Return ONLY the sentences you changed, as JSON {\"id\": \"corrected sentence\"}. "
    "If nothing needs a change, return {}."
)

_MAX_ITEMS_PER_CALL = 40
_MAX_CHARS_PER_CALL = 5000
_MAX_RETRIES = 2
_REQUEST_TIMEOUT = 90.0


class AICorrector:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=_REQUEST_TIMEOUT,
            max_retries=2,
        )
        self._model = config.OPENAI_MODEL
        self._sem = asyncio.Semaphore(config.AI_CONCURRENCY)

    async def proofread(self, sentences: list[str]) -> dict[int, str]:
        """Gaplar ro'yxati -> {indeks: tuzatilgan gap} (faqat AI o'zgartirganlari)."""
        if not sentences or not config.OPENAI_API_KEY:
            return {}
        tasks = [self._proofread_batch(sentences, start, end)
                 for start, end in self._make_batches(sentences)]
        result: dict[int, str] = {}
        for part in await asyncio.gather(*tasks):
            result.update(part)
        return result

    def _make_batches(self, items: list[str]) -> list[tuple[int, int]]:
        batches: list[tuple[int, int]] = []
        start = count = chars = 0
        for i, item in enumerate(items):
            size = len(item)
            if count and (count >= _MAX_ITEMS_PER_CALL or chars + size > _MAX_CHARS_PER_CALL):
                batches.append((start, i))
                start, count, chars = i, 0, 0
            count += 1
            chars += size
        batches.append((start, len(items)))
        return batches

    async def _proofread_batch(self, items: list[str], start: int, end: int) -> dict[int, str]:
        payload = {str(i - start): items[i] for i in range(start, end)}
        async with self._sem:
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    response = await self._client.chat.completions.create(
                        model=self._model,
                        temperature=0,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": _PROOFREAD_PROMPT},
                            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                        ],
                    )
                    await self._record_usage(getattr(response, "usage", None))
                    data = json.loads(response.choices[0].message.content or "{}")
                    if not isinstance(data, dict):
                        return {}
                    out = {}
                    for key, value in data.items():
                        if isinstance(value, str) and key.isdigit() and int(key) < end - start:
                            out[start + int(key)] = value
                    return out
                except Exception as exc:  # noqa: BLE001
                    logger.warning("AI so'rov xatosi (urinish %s): %s", attempt + 1, exc)
                    await asyncio.sleep(1.0 * (attempt + 1))
        return {}

    async def _record_usage(self, usage) -> None:
        if not usage:
            return
        prices = config.OPENAI_PRICES.get(self._model)
        if not prices:
            return
        price_in, price_out = prices
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = prompt_tokens / 1_000_000 * price_in + completion_tokens / 1_000_000 * price_out
        try:
            async with session_maker() as session:
                repo = SettingRepository(session)
                await repo.increment("ai_cost_usd", cost)
                await repo.increment("ai_tokens", prompt_tokens + completion_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI xarajatini yozishda xato: %s", exc)
