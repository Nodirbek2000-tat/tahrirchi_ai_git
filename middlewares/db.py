from contextvars import ContextVar

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

# Bitta update davomida ochilgan sessiyalar (update tugaganda albatta yopiladi)
_open_sessions: ContextVar[list | None] = ContextVar("open_db_sessions", default=None)


class DbSessionMiddleware(BaseMiddleware):
    """Har bir message/callback uchun bitta DB sessiya ochib, repozitoriylarni beradi.

    Muhim: ma'lumot handlerlarga yetib borishi uchun sessiya message va callback_query
    darajasida ochiladi. Lekin aiogram 2 da keyingi middleware (masalan, majburiy obuna)
    CancelHandler bersa yoki xato chiqsa, message darajasidagi post_process CHAQIRILMAYDI —
    sessiya ochiq qolib, bazaga ulanishlar tugab qolardi ("QueuePool limit reached").
    Shuning uchun sessiyalar update darajasida ham kuzatiladi va update tugaganda
    (finally ichida, har doim) yopiladi.
    """

    async def _open(self, data: dict):
        session = session_maker()
        opened = _open_sessions.get()
        if opened is not None:
            opened.append(session)
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

    # --- Update (har doim oxirida chaqiriladi) ---
    async def on_pre_process_update(self, update, data: dict):
        _open_sessions.set([])

    async def on_post_process_update(self, update, results, data: dict):
        opened = _open_sessions.get()
        if opened:
            for session in opened:
                await session.close()   # qayta yopish xavfsiz
            opened.clear()

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
