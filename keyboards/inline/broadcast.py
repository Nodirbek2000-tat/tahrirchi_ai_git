from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.inline.callbacks import broadcast_cb


def confirm_broadcast_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Yuborish", callback_data=broadcast_cb.new(action="send")),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=broadcast_cb.new(action="cancel")),
    )
    return kb


def ad_markup(btn_name: str | None, btn_url: str | None) -> InlineKeyboardMarkup | None:
    if btn_name and btn_url:
        return InlineKeyboardMarkup().add(InlineKeyboardButton(btn_name, url=btn_url))
    return None
