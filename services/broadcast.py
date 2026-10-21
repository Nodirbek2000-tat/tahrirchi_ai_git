"""Reklamani barcha foydalanuvchilarga sekin, ketma-ket (flood'siz) yuborish."""

import asyncio
import logging

from aiogram.utils import exceptions

from keyboards.inline.broadcast import ad_markup

logger = logging.getLogger(__name__)

_DELAY = 0.05  # ~20 xabar/soniya (Telegram limitidan past)


async def _send_one(bot, user_id, text, photo, markup, retries=1) -> bool:
    try:
        if photo:
            await bot.send_photo(user_id, photo, caption=text, reply_markup=markup)
        else:
            await bot.send_message(user_id, text, reply_markup=markup)
        return True
    except exceptions.RetryAfter as e:
        if retries > 0:
            await asyncio.sleep(e.timeout + 1)
            return await _send_one(bot, user_id, text, photo, markup, retries - 1)
        return False
    except exceptions.TelegramAPIError:
        return False  # bloklagan / o'chirilgan / topilmadi
    except Exception as exc:  # noqa: BLE001
        logger.warning("Broadcast xato (%s): %s", user_id, exc)
        return False


async def run_personal(bot, messages: list[tuple[int, str]]) -> tuple[int, int]:
    """Har bir userga o'z matnini yuboradi (masalan, sovg'a + shaxsiy balans)."""
    sent = 0
    failed = 0
    for user_id, text in messages:
        if await _send_one(bot, user_id, text, None, None):
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(_DELAY)
    return sent, failed


async def run_broadcast(
    bot, user_ids: list[int], text: str, photo: str | None,
    btn_name: str | None, btn_url: str | None,
) -> tuple[int, int]:
    markup = ad_markup(btn_name, btn_url)
    sent = 0
    failed = 0
    for user_id in user_ids:
        ok = await _send_one(bot, user_id, text, photo, markup)
        if ok:
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(_DELAY)
    return sent, failed
