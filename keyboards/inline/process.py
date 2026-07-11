from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.inline.callbacks import process_cb


def confirm_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("▶️ Tahrirni boshlash", callback_data=process_cb.new(action="start")),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=process_cb.new(action="cancel")),
    )
    return kb
