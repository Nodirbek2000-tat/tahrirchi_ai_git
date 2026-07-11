from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Setting


class SettingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> float:
        row = await self.session.get(Setting, key)
        return row.value if row else 0.0

    async def increment(self, key: str, amount: float) -> None:
        """Atomik oshirish (UPSERT)."""
        stmt = (
            insert(Setting)
            .values(key=key, value=amount)
            .on_conflict_do_update(
                index_elements=[Setting.key],
                set_={"value": Setting.value + amount},
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()
