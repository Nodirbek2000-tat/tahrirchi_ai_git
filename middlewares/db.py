from aiogram.dispatcher.middlewares import BaseMiddleware

from db import session_maker
from db.repositories import (
    AdminRepository,
    ChannelRepository,
    PaymentRepository,
    SettingRepository,
    StatsRepository,
    TaskRepository,
    UserRepository,
)


class DbSessionMiddleware(BaseMiddleware):
    """Har bir message/callback uchun bitta DB sessiya ochib, repozitoriylarni beradi.

    Muhim: ma'lumot handlerlarga yetib borishi uchun aynan message va
    callback_query darajasidagi hooklardan foydalaniladi (update darajasi emas).
    """

    async def _open(self, data: dict):
        session = session_maker()
        data["session"] = session
        data["users"] = UserRepository(session)
        data["payments"] = PaymentRepository(session)
        data["tasks"] = TaskRepository(session)
        data["admins"] = AdminRepository(session)
        data["channels"] = ChannelRepository(session)
        data["settings"] = SettingRepository(session)
        data["stats"] = StatsRepository(session)

    async def _close(self, data: dict):
        session = data.get("session")
        if session is not None:
            await session.close()

    # --- Message ---
    async def on_pre_process_message(self, message, data: dict):
        await self._open(data)

    async def on_post_process_message(self, message, results, data: dict):
        await self._close(data)

    # --- Callback query ---
    async def on_pre_process_callback_query(self, call, data: dict):
        await self._open(data)

    async def on_post_process_callback_query(self, call, results, data: dict):
        await self._close(data)
