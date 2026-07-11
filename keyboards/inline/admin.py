from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.inline.callbacks import review_cb


def review_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(
            "✅ Tasdiqlash", callback_data=review_cb.new(action="approve", payment_id=payment_id)
        ),
        InlineKeyboardButton(
            "❌ Rad etish", callback_data=review_cb.new(action="reject", payment_id=payment_id)
        ),
    )
    return kb
