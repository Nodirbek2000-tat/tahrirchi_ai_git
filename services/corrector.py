"""Yakuniy matn tuzatuvchi: AI imlo tuzatishi + yangi alifbo o'girishi."""

from services.ai import AICorrector
from services.transliteration import to_new_alphabet


class TextCorrector:
    def __init__(self, ai: AICorrector | None = None) -> None:
        self.ai = ai or AICorrector()

    async def correct_many(self, segments: list[str]) -> list[str]:
        """1) AI imloni tuzatadi  2) yangi alifboga o'giradi."""
        corrected = await self.ai.correct(segments)
        return [to_new_alphabet(text) for text in corrected]
