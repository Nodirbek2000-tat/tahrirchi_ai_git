from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.inline.callbacks import script_cb

DIRECTION_LABELS = {
    "cyr2lat": "Кирилл → Lotin (oʻzbek, sh)",
    "cyr2new": "Кирилл → Yangi lotin (özbek, ş)",
    "lat2cyr": "Lotin → Кирилл (ўзбек)",
}


def direction_keyboard(directions: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for direction in directions:
        kb.add(
            InlineKeyboardButton(
                DIRECTION_LABELS[direction], callback_data=script_cb.new(dir=direction)
            )
        )
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data=script_cb.new(dir="cancel")))
    return kb
