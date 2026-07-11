"""OpenAI xizmati: imlo tuzatish VA tarjima.

Matn bo'laklari INDEKSLI JSON obyekt ko'rinishida yuboriladi:
    {"0": "matn", "1": "matn", ...}
AI aynan o'sha kalitlar bilan qaytaradi. Biror kalit yo'qolsa/xato bo'lsa —
faqat o'sha bo'lak asl holida qoladi (fayl hech qachon buzilmaydi).

Ishonchlilik: kichik guruhlar, cheklangan parallel so'rovlar (semaphore),
har so'rovga timeout.
"""

import asyncio
import json
import logging

from openai import AsyncOpenAI

from data import config
from db import session_maker
from db.repositories.setting import SettingRepository

logger = logging.getLogger(__name__)

_CORRECT_PROMPT = (
    "Siz o'zbek tili (lotin) uchun imlo va grammatika muharririsiz. "
    "Sizga JSON obyekt beriladi: kalit — raqamli indeks, qiymat — matn bo'lagi. "
    "Har bir qiymatdagi imloviy va grammatik xatolarni to'g'irlang.\n"
    "QAT'IY QOIDALAR:\n"
    "1. Matnni tarjima QILMANG, tilini o'zgartirmang.\n"
    "2. Mazmun, ma'no va gap tuzilishini saqlang — faqat xatolarni tuzating.\n"
    "3. BARCHA kalitlarni aynan o'sha nomlar bilan qaytaring, birontasini tashlamang.\n"
    "4. Bo'sh yoki faqat belgi/raqamdan iborat qiymatlarni o'zgartirmang.\n"
    "5. Hech qanday izoh yozmang.\n"
    'Javob faqat JSON: {"0": "...", "1": "...", ...} — kirish bilan bir xil kalitlar.'
)

_LANG_FULL = {
    "ru": "rus (Russian)",
    "uz": "o'zbek (Uzbek, lotin)",
    "en": "ingliz (English)",
}


def _translate_prompt(target_lang: str) -> str:
    target = _LANG_FULL.get(target_lang, target_lang)
    return (
        f"Siz professional tarjimonsiz. Sizga JSON obyekt beriladi: "
        f"kalit — raqamli indeks, qiymat — matn bo'lagi. "
        f"Har bir qiymatni TO'LIQ {target} tiliga aniq va tabiiy tarjima qiling.\n"
        "QAT'IY QOIDALAR:\n"
        f"1. HAR BIR so'zni {target} tiliga tarjima qiling. Manba tilida (o'zbek, "
        "rus yoki ingliz) BIRORTA ham so'z qolmasin — hatto bitta so'z bo'lsa ham tarjima qiling.\n"
        "2. Ma'noni to'liq saqlang, xatosiz va ravon tarjima qiling.\n"
        "3. BARCHA kalitlarni aynan o'sha nomlar bilan qaytaring, birontasini tashlamang.\n"
        "4. Faqat raqam, belgi yoki nuqta-chiziqdan iborat qiymatlarni o'zgartirmang.\n"
        "5. Atoqli ismlar va lotincha ilmiy nomlar (masalan Cucumis melo) o'zgarmasin.\n"
        "6. Hech qanday izoh yozmang.\n"
        'Javob faqat JSON: {"0": "...", "1": "...", ...} — kirish bilan bir xil kalitlar.'
    )


_MAX_ITEMS_PER_CALL = 30
_MAX_CHARS_PER_CALL = 4000
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

    # --- Ommaviy metodlar ---
    async def correct(self, segments: list[str]) -> list[str]:
        return await self._run(segments, _CORRECT_PROMPT)

    async def translate(self, segments: list[str], target_lang: str) -> list[str]:
        return await self._run(segments, _translate_prompt(target_lang))

    # --- Ichki ish ---
    async def _run(self, segments: list[str], system_prompt: str) -> list[str]:
        if not segments:
            return []
        result: list[str] = list(segments)  # sukut — asl matn (hech narsa yo'qolmaydi)
        tasks = [
            self._run_batch(segments, start, end, system_prompt)
            for start, end in self._make_batches(segments)
        ]
        for (start, end), out in await asyncio.gather(*tasks):
            result[start:end] = out
        return result

    def _make_batches(self, segments: list[str]) -> list[tuple[int, int]]:
        batches: list[tuple[int, int]] = []
        start = 0
        count = 0
        chars = 0
        for i, seg in enumerate(segments):
            seg_len = len(seg or "")
            if count and (count >= _MAX_ITEMS_PER_CALL or chars + seg_len > _MAX_CHARS_PER_CALL):
                batches.append((start, i))
                start, count, chars = i, 0, 0
            count += 1
            chars += seg_len
        batches.append((start, len(segments)))
        return batches

    async def _run_batch(
        self, segments: list[str], start: int, end: int, system_prompt: str
    ) -> tuple[tuple[int, int], list[str]]:
        chunk = segments[start:end]
        out = list(chunk)  # sukut — asl matn
        remaining = [i for i in range(len(chunk)) if (chunk[i] or "").strip()]

        async with self._sem:
            for attempt in range(_MAX_RETRIES + 1):
                if not remaining:
                    break
                payload = {str(i): (chunk[i] or "") for i in remaining}
                try:
                    response = await self._client.chat.completions.create(
                        model=self._model,
                        temperature=0,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                        ],
                    )
                    await self._record_usage(getattr(response, "usage", None))
                    data = json.loads(response.choices[0].message.content)
                    if isinstance(data, dict):
                        # Faqat tashlab ketilgan/xato bo'laklarni qayta so'raymiz
                        still_missing = []
                        for i in remaining:
                            value = data.get(str(i))
                            if isinstance(value, str):
                                out[i] = value
                            else:
                                still_missing.append(i)
                        remaining = still_missing
                    else:
                        logger.warning("AI javobi obyekt emas")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("AI so'rov xatosi (urinish %s): %s", attempt + 1, exc)
                    await asyncio.sleep(1.0 * (attempt + 1))

        return (start, end), out

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
