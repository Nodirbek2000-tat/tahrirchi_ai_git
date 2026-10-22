"""Kim faylni tahrirlay oladi: admin, premium yoki bepul fayli qolgan user.

Barcha bo'limlar (alifbo, kirill↔lotin, imlo) shu yerdan foydalanadi:
    access = await check(users, admins, user_id)   # fayl qabul qilinganda
    ok = await consume(users, access)               # tahrir boshlanganda
    await refund(users, access)                     # xatolik bo'lsa
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from data import config
from db.repositories import AdminRepository, SettingRepository, UserRepository

TASHKENT = timezone(timedelta(hours=5))


@dataclass
class Access:
    user_id: int
    kind: str                         # admin | premium | free | none
    free_left: int = 0
    premium_until: datetime | None = None

    @property
    def allowed(self) -> bool:
        return self.kind != "none"

    def to_state(self) -> dict:
        return asdict(self)

    @classmethod
    def from_state(cls, data: dict | None, user_id: int) -> "Access":
        return cls(**data) if data else cls(user_id, "none")


def fmt_date(value: datetime | None) -> str:
    return value.astimezone(TASHKENT).strftime("%d.%m.%Y") if value else "—"


def fmt_som(value: int) -> str:
    return f"{value:,}".replace(",", " ")


async def check(
    users: UserRepository, admins: AdminRepository, settings: SettingRepository, tg_user
) -> Access:
    """tg_user — aiogram User. /start bosmagan user ham shu yerda ro'yxatga olinadi."""
    user_id = tg_user.id
    if await admins.is_admin(user_id):
        return Access(user_id, "admin")
    user, _ = await users.get_or_create(
        user_id, tg_user.full_name, tg_user.username, await free_files_default(settings)
    )
    if user.is_premium:
        return Access(user_id, "premium", user.free_files, user.premium_until)
    if user.free_files > 0:
        return Access(user_id, "free", user.free_files)
    return Access(user_id, "none")


async def consume(users: UserRepository, access: Access) -> bool:
    """Tahrir boshlanganda: bepul userdan bitta fayl yechiladi (atomik)."""
    if access.kind in ("admin", "premium"):
        return True
    if access.kind == "free":
        return await users.use_free_file(access.user_id)
    return False


async def refund(users: UserRepository, access: Access) -> None:
    if access.kind == "free":
        await users.return_free_file(access.user_id)


def status_line(access: Access) -> str:
    """Tasdiqlash xabaridagi qator."""
    if access.kind == "admin":
        return "👑 Admin — <b>bepul</b>."
    if access.kind == "premium":
        return f"💎 Premium — cheksiz · {fmt_date(access.premium_until)} gacha."
    return (
        f"🎁 Bepul fayl: <b>{access.free_left}</b> ta qoldi "
        f"(bu fayldan keyin: {access.free_left - 1})."
    )


async def after_line(users: UserRepository, access: Access) -> str:
    """Tayyor fayl ostidagi qator."""
    if access.kind == "admin":
        return "👑 Admin — bepul."
    if access.kind == "premium":
        return f"💎 Premium: {fmt_date(access.premium_until)} gacha."
    user = await users.get(access.user_id)
    left = user.free_files if user else 0
    if left:
        return f"🎁 Bepul fayllar qoldi: <b>{left}</b> ta."
    return "🎁 Bepul fayllar tugadi. Cheksiz foydalanish uchun — 💎 Premium."


async def premium_price(settings: SettingRepository) -> int:
    return int(await settings.get_value(config.SETTING_PREMIUM_PRICE, config.PREMIUM_PRICE))


async def free_files_default(settings: SettingRepository) -> int:
    return int(await settings.get_value(config.SETTING_FREE_FILES, config.FREE_FILES))


def premium_offer(price: int) -> str:
    return (
        "💎 <b>Premium</b> — barcha imkoniyatlar cheksiz:\n"
        "• yangi alifboga o'girish\n"
        "• kirill ↔ lotin\n"
        "• imlo, tinish belgilari va katta harflarni tuzatish\n"
        "• Word, Excel, PowerPoint, PDF, TXT — istalgancha fayl\n\n"
        f"💵 Narxi: <b>{fmt_som(price)} so'm</b> / {config.PREMIUM_DAYS} kun"
    )


NO_ACCESS = "🎁 Bepul fayllaringiz tugadi."
