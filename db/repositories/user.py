from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


class UserRepository:
    """Foydalanuvchilar ustidan barcha DB amallari."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_or_create(
        self,
        user_id: int,
        full_name: str,
        username: str | None,
        free_files: int | None = None,
    ) -> tuple[User, bool]:
        user = await self.session.get(User, user_id)
        if user:
            return user, False

        user = User(id=user_id, full_name=full_name, username=username)
        if free_files is not None:
            user.free_files = free_files  # admin paneldagi joriy qiymat
        self.session.add(user)
        await self.session.commit()
        return user, True

    # --- Bepul fayllar ---
    async def use_free_file(self, user_id: int) -> bool:
        """Bitta bepul faylni ishlatish (atomik). Qolgan bo'lsa True."""
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id, User.free_files > 0)
            .values(free_files=User.free_files - 1)
            .returning(User.id)
        )
        await self.session.commit()
        return result.scalar_one_or_none() is not None

    async def return_free_file(self, user_id: int) -> None:
        """Xatolik bo'lsa ishlatilgan bepul faylni qaytarish."""
        await self.session.execute(
            update(User).where(User.id == user_id).values(free_files=User.free_files + 1)
        )
        await self.session.commit()

    async def add_free_files_all(self, amount: int) -> int:
        """Barcha userlarga bepul fayl qo'shadi (bitta SQL). Nechta userga qo'shilganini qaytaradi."""
        result = await self.session.execute(
            update(User).values(free_files=User.free_files + amount)
        )
        await self.session.commit()
        return result.rowcount or 0

    async def free_files_list(self) -> list[tuple[int, int]]:
        """Barcha userlarning (id, bepul fayllar soni) ro'yxati."""
        result = await self.session.execute(select(User.id, User.free_files))
        return [(row[0], row[1]) for row in result.all()]

    # --- Premium ---
    async def extend_premium(self, user_id: int, days: int) -> datetime | None:
        """Premiumni uzaytiradi: amaldagi muddat tugamagan bo'lsa — uning ustiga qo'shiladi."""
        now = datetime.now(timezone.utc)
        base = func.greatest(func.coalesce(User.premium_until, now), now)
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(premium_until=base + timedelta(days=days))
            .returning(User.premium_until)
        )
        await self.session.commit()
        return result.scalar_one_or_none()

    async def count_premium(self) -> int:
        result = await self.session.execute(
            select(func.count(User.id)).where(User.premium_until > datetime.now(timezone.utc))
        )
        return int(result.scalar_one())

    # --- Umumiy ---
    async def count(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return int(result.scalar_one())

    async def all_ids(self) -> list[int]:
        result = await self.session.execute(
            select(User.id).where(User.is_blocked == False)  # noqa: E712
        )
        return [row[0] for row in result.all()]
