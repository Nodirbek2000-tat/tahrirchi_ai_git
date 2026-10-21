from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from data import config
from keyboards.inline.callbacks import buy_cb, receipt_cb


def packages_keyboard(token_price: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for package, tokens in config.PACKAGE_TOKENS.items():
        amount = tokens * token_price
        kb.add(
            InlineKeyboardButton(
                text=f"{tokens} token — {amount:,} so'm".replace(",", " "),
                callback_data=buy_cb.new(package=package),
            )
        )
    return kb


def receipt_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            text="✅ Chek yuborish",
            callback_data=receipt_cb.new(payment_id=payment_id),
        )
    )
    return kb
