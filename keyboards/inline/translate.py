from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.inline.callbacks import translate_lang_cb
from services.translation import LANG_NAMES


def language_keyboard(targets: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        *[
            InlineKeyboardButton(
                LANG_NAMES.get(lang, lang),
                callback_data=translate_lang_cb.new(lang=lang),
            )
            for lang in targets
        ]
    )
    kb.add(
        InlineKeyboardButton(
            "❌ Bekor qilish", callback_data=translate_lang_cb.new(lang="cancel")
        )
    )
    return kb
