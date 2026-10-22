"""Matnni o'girish: user yuborgan matn darhol boshqa yozuvga o'giriladi.

Imlo va mazmun o'zgarmaydi — faqat harflar. Natija ostidagi tugmalar bilan boshqa
yozuvda ham ko'rish mumkin (bu qo'shimcha urinish hisoblanmaydi).
Bepul userga config.FREE_TEXTS ta urinish, premium/adminga cheksiz.
"""

import html

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from data import config
from db.repositories import AdminRepository, SettingRepository, UserRepository
from keyboards.default import BTN_TEXT
from keyboards.inline import premium_keyboard
from keyboards.inline.callbacks import text_cb
from loader import dp
from services.access import free_files_default, premium_offer, premium_price
from services.text_convert import TARGET_LABELS, analyze, convert, default_target

_CHUNK = 4000   # Telegram xabari 4096 belgigacha


def _keyboard(current: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for target, label in TARGET_LABELS.items():
        mark = "✅ " if target == current else "🔁 "
        kb.add(InlineKeyboardButton(mark + label, callback_data=text_cb.new(to=target)))
    return kb


def _chunks(text: str) -> list[str]:
    """Uzun matnni qator chegarasida bo'lish."""
    parts, buf = [], ""
    for line in text.split("\n"):
        while len(line) > _CHUNK:
            if buf:
                parts.append(buf)
                buf = ""
            parts.append(line[:_CHUNK])
            line = line[_CHUNK:]
        if len(buf) + len(line) + 1 > _CHUNK:
            parts.append(buf)
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    if buf:
        parts.append(buf)
    return parts or [text]


async def _send(original: types.Message, text: str, target: str):
    chunks = _chunks(text)
    for i, chunk in enumerate(chunks):
        last = i == len(chunks) - 1
        await original.reply(html.escape(chunk), reply_markup=_keyboard(target) if last else None)


@dp.message_handler(text=BTN_TEXT, state="*")
async def text_menu(
    message: types.Message, users: UserRepository, admins: AdminRepository,
    settings: SettingRepository, state: FSMContext,
):
    await state.finish()
    user, _ = await users.get_or_create(
        message.from_user.id, message.from_user.full_name, message.from_user.username,
        await free_files_default(settings),
    )
    if await admins.is_admin(user.id):
        limit = "👑 Admin — cheksiz."
    elif user.is_premium:
        limit = "💎 Premium — cheksiz."
    else:
        limit = f"🎁 Bepul urinishlar: <b>{user.free_texts}</b> ta qoldi (Premiumda cheksiz)."
    await message.answer(
        "💬 <b>Matnni o'girish</b>\n\n"
        "Istalgan matnni shu yerga yozing yoki yuboring — darhol o'girib beraman:\n"
        "• lotin → yangi alifbo (sh→ş, ch→ç, gʻ→ğ, oʻ→ö)\n"
        "• kirill → lotin (yangi yoki eski alifbo)\n"
        "• natija ostidagi tugmalar bilan boshqa yozuvda ham olasiz\n\n"
        "ℹ️ Imlo va mazmun o'zgarmaydi — faqat harflar. Ruscha matnga tegilmaydi.\n\n"
        f"{limit}"
    )


@dp.message_handler(lambda m: m.text and not m.text.startswith("/"),
                    content_types=[types.ContentType.TEXT], state=None)
async def convert_text(
    message: types.Message, users: UserRepository, admins: AdminRepository,
    settings: SettingRepository,
):
    text = message.text
    target = default_target(analyze(text))
    if target is None:
        await message.reply(
            "🔎 Bu matnda o'giriladigan o'zbekcha harf topilmadi.\n"
            "(Ruscha matn o'girilmaydi — bu tarjima emas.)"
        )
        return
    result = convert(text, target)
    if result == text:
        await message.reply("✅ Matn allaqachon shu yozuvda — o'zgartirish shart emas.",
                            reply_markup=_keyboard(target))
        return

    user, _ = await users.get_or_create(
        message.from_user.id, message.from_user.full_name, message.from_user.username,
        await free_files_default(settings),
    )
    unlimited = user.is_premium or await admins.is_admin(user.id)
    if not unlimited and not await users.use_free_text(user.id):
        price = await premium_price(settings)
        await message.reply(
            f"🎁 Bepul {config.FREE_TEXTS} ta urinishingiz tugadi.\n\n" + premium_offer(price),
            reply_markup=premium_keyboard(price),
        )
        return
    await _send(message, result, target)


@dp.callback_query_handler(text_cb.filter(), state="*")
async def switch_target(call: types.CallbackQuery, callback_data: dict):
    original = call.message.reply_to_message
    if original is None or not original.text:
        await call.answer("Asl matn topilmadi — matnni qaytadan yuboring.", show_alert=True)
        return
    target = callback_data["to"]
    result = convert(original.text, target)
    await call.answer(TARGET_LABELS.get(target, ""))
    chunks = _chunks(result)
    if len(chunks) == 1:
        try:
            await call.message.edit_text(html.escape(result), reply_markup=_keyboard(target))
        except Exception:  # noqa: BLE001 — matn o'zgarmagan bo'lsa Telegram xato beradi
            pass
        return
    await _send(original, result, target)
