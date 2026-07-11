from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def subscription_keyboard(channels) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for channel in channels:
        if channel.username:
            kb.add(
                InlineKeyboardButton(
                    f"📢 {channel.title}",
                    url=f"https://t.me/{channel.username}",
                )
            )
    kb.add(InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return kb
