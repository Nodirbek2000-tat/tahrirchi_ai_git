from aiogram import types

from db.repositories import UserRepository
from keyboards.default import (
    BTN_BALANCE,
    BTN_BUY,
    BTN_EXCEL,
    BTN_PDF,
    BTN_PPTX,
    BTN_WORD,
)
from keyboards.inline import packages_keyboard
from loader import dp

# Fayl turi tugmalari -> foydalanuvchini yo'naltirish
_FILE_PROMPTS = {
    BTN_WORD: "📝 <b>Word</b> hujjatini (.docx) shu yerga yuboring.",
    BTN_EXCEL: "📊 <b>Excel</b> faylini (.xlsx) shu yerga yuboring.",
    BTN_PDF: "📕 <b>PDF</b> faylini (.pdf) shu yerga yuboring.",
    BTN_PPTX: "📽 <b>Prezentatsiya</b> faylini (.pptx) shu yerga yuboring.",
}


@dp.message_handler(lambda m: m.text in _FILE_PROMPTS, state="*")
async def ask_file(message: types.Message):
    await message.answer(_FILE_PROMPTS[message.text])


@dp.message_handler(text=BTN_BALANCE, state="*")
async def show_balance(message: types.Message, users: UserRepository):
    user = await users.get(message.from_user.id)
    tokens = user.tokens if user else 0
    await message.answer(f"💰 Balansingiz: <b>{tokens}</b> token.")


@dp.message_handler(text=BTN_BUY, state="*")
async def show_packages(message: types.Message):
    await message.answer(
        "🛒 <b>Token paketini tanlang:</b>\n\n1 token = 500 so'm",
        reply_markup=packages_keyboard(),
    )
