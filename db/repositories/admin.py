from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from data import config
from db.models import Admin


class AdminRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_admin(self, user_id: int) -> bool:
        if user_id in config.ADMINS:  # .env dagi super-adminlar
            return True
        return await self.session.get(Admin, user_id) is not None

    async def add(self, user_id: int, added_by: int | None) -> None:
        if await self.session.get(Admin, user_id) is None:
            self.session.add(Admin(user_id=user_id, added_by=added_by))
            await self.session.commit()

    async def remove(self, user_id: int) -> None:
        await self.session.execute(delete(Admin).where(Admin.user_id == user_id))
        await self.session.commit()

    async def list_ids(self) -> list[int]:
        result = await self.session.execute(select(Admin.user_id))
        db_ids = [row[0] for row in result.all()]
        # .env super-adminlar + bazadagilar (takrorsiz)
        return sorted(set(config.ADMINS) | set(db_ids))
