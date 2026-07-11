from aiogram import types
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware


class PrivateOnlyMiddleware(BaseMiddleware):
    """Bot faqat shaxsiy chatda ishlaydi. Guruh/kanal xabarlari e'tiborsiz qoladi.

    (Callback query'lar to'xtatilmaydi — admin to'lov tugmalari kanalda ishlashi kerak.)
    """

    async def on_pre_process_message(self, message: types.Message, data: dict):
        if message.chat.type != types.ChatType.PRIVATE:
            raise CancelHandler()

    async def on_pre_process_edited_message(self, message: types.Message, data: dict):
        if message.chat.type != types.ChatType.PRIVATE:
            raise CancelHandler()
