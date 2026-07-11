"""Majburiy obuna tekshiruvi (qisqa muddatli kesh bilan)."""

import time

_MEMBER_STATUSES = {"creator", "administrator", "member"}
_CACHE_TTL = 120  # soniya
_cache: dict[tuple, tuple] = {}  # (user_id, target) -> (subscribed: bool, expiry)


def _target(channel) -> str | int | None:
    if channel.chat_id:
        return channel.chat_id
    if channel.username:
        return f"@{channel.username}"
    return None


async def is_subscribed(bot, user_id: int, target) -> bool | None:
    """True/False, yoki None (tekshirib bo'lmadi — bloklamaymiz)."""
    key = (user_id, target)
    now = time.time()
    cached = _cache.get(key)
    if cached and cached[1] > now:
        return cached[0]
    try:
        member = await bot.get_chat_member(target, user_id)
        ok = member.status in _MEMBER_STATUSES or (
            member.status == "restricted" and getattr(member, "is_chat_member", False)
        )
        _cache[key] = (ok, now + _CACHE_TTL)
        return ok
    except Exception:
        return None


def invalidate(user_id: int) -> None:
    """Foydalanuvchi keshini tozalash (masalan, «Tekshirish» bosilganda)."""
    for key in [k for k in _cache if k[0] == user_id]:
        _cache.pop(key, None)


async def unsubscribed_channels(bot, user_id: int, channels) -> list:
    """Foydalanuvchi obuna bo'lmagan kanallar ro'yxati."""
    missing = []
    for channel in channels:
        target = _target(channel)
        if target is None:
            continue
        ok = await is_subscribed(bot, user_id, target)
        if ok is False:  # None => tekshirib bo'lmadi => bloklamaymiz
            missing.append(channel)
    return missing
