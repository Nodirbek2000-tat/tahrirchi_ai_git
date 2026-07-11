from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SubChannel


class ChannelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def all(self) -> list[SubChannel]:
        result = await self.session.execute(select(SubChannel).order_by(SubChannel.id))
        return list(result.scalars().all())

    async def get(self, channel_id: int) -> SubChannel | None:
        return await self.session.get(SubChannel, channel_id)

    async def add(
        self, chat_id: int | None, username: str | None, title: str, added_by: int | None
    ) -> SubChannel:
        channel = SubChannel(
            chat_id=chat_id, username=username, title=title, added_by=added_by
        )
        self.session.add(channel)
        await self.session.commit()
        await self.session.refresh(channel)
        return channel

    async def remove(self, channel_id: int) -> None:
        channel = await self.session.get(SubChannel, channel_id)
        if channel:
            await self.session.delete(channel)
            await self.session.commit()
