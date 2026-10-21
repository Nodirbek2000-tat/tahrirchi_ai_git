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
        free_tokens: int | None = None,
    ) -> tuple[User, bool]:
        user = await self.session.get(User, user_id)
        if user:
            return user, False

        user = User(id=user_id, full_name=full_name, username=username)
        if free_tokens is not None:
            user.tokens = free_tokens  # admin paneldagi joriy qiymat
        self.session.add(user)
        await self.session.commit()
        return user, True

    async def add_tokens(self, user_id: int, amount: int) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(tokens=User.tokens + amount)
        )
        await self.session.commit()

    async def deduct_tokens(self, user_id: int, amount: int) -> bool:
        """Token yechish (atomik). Yetarli bo'lsa True, aks holda False."""
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id, User.tokens >= amount)
            .values(tokens=User.tokens - amount)
            .returning(User.id)
        )
        await self.session.commit()
        return result.scalar_one_or_none() is not None

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return int(result.scalar_one())

    async def add_tokens_all(self, amount: int) -> int:
        """Barcha userlarga token qo'shadi (bitta SQL so'rov). Nechta userga qo'shilganini qaytaradi."""
        result = await self.session.execute(
            update(User).values(tokens=User.tokens + amount)
        )
        await self.session.commit()
        return result.rowcount or 0

    async def balances(self) -> list[tuple[int, int]]:
        """Barcha userlarning (id, token) ro'yxati."""
        result = await self.session.execute(select(User.id, User.tokens))
        return [(row[0], row[1]) for row in result.all()]

    async def all_ids(self) -> list[int]:
        result = await self.session.execute(
            select(User.id).where(User.is_blocked == False)  # noqa: E712
        )
        return [row[0] for row in result.all()]
