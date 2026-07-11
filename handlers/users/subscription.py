from aiogram import types

from db.repositories import ChannelRepository
from loader import bot, dp
from services.subscription import invalidate, unsubscribed_channels


@dp.callback_query_handler(text="check_sub", state="*")
async def check_subscription(call: types.CallbackQuery, channels: ChannelRepository):
    invalidate(call.from_user.id)
    channel_list = await channels.all()
    missing = await unsubscribed_channels(bot, call.from_user.id, channel_list)
    if missing:
        await call.answer(
            "❗ Hali barcha kanallarga obuna bo'lmadingiz.", show_alert=True
        )
        return
    await call.answer("✅ Rahmat!")
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(
        "✅ Obuna tasdiqlandi! Endi menga <b>fayl</b> yuboring yoki /start bosing."
    )
