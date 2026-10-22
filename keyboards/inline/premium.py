from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from data import config
from keyboards.inline.callbacks import buy_cb, receipt_cb


def premium_keyboard(price: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(
            text=f"💎 Premium olish — {price:,} so'm / {config.PREMIUM_DAYS} kun".replace(",", " "),
            callback_data=buy_cb.new(package=config.PREMIUM_PACKAGE),
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
