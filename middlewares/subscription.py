from aiogram import types
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware

from keyboards.inline.subscription import subscription_keyboard
from loader import bot
from services.subscription import unsubscribed_channels

GATE_TEXT = "🔒 Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:"


class SubscriptionMiddleware(BaseMiddleware):
    """Majburiy obuna. Adminlar va obuna bo'lganlar o'tadi."""

    async def on_pre_process_message(self, message: types.Message, data: dict):
        await self._gate(message.from_user.id, message, data, is_callback=False)

    async def on_pre_process_callback_query(self, call: types.CallbackQuery, data: dict):
        if call.data == "check_sub":  # tekshirish tugmasi o'tsin
            return
        await self._gate(call.from_user.id, call, data, is_callback=True)

    async def _gate(self, user_id: int, event, data: dict, is_callback: bool):
        admins = data.get("admins")
        channels_repo = data.get("channels")
        if admins is None or channels_repo is None:
            return
        if await admins.is_admin(user_id):
            return
        channels = await channels_repo.all()
        if not channels:
            return
        missing = await unsubscribed_channels(bot, user_id, channels)
        if not missing:
            return

        kb = subscription_keyboard(missing)
        if is_callback:
            await event.answer("Avval obuna bo'ling!", show_alert=True)
            await event.message.answer(GATE_TEXT, reply_markup=kb)
        else:
            await event.answer(GATE_TEXT, reply_markup=kb)
        raise CancelHandler()
