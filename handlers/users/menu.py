from aiogram import types

from db.repositories import AdminRepository, SettingRepository, UserRepository
from keyboards.default import (
    BTN_ACCOUNT,
    BTN_EXCEL,
    BTN_PDF,
    BTN_PPTX,
    BTN_PREMIUM,
    BTN_WORD,
    LEGACY_BUTTONS,
    main_menu,
)
from keyboards.inline import premium_keyboard
from loader import dp
from services.access import fmt_date, premium_offer, premium_price

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


@dp.message_handler(text=BTN_ACCOUNT, state="*")
async def show_account(
    message: types.Message,
    users: UserRepository,
    admins: AdminRepository,
    settings: SettingRepository,
):
    user = await users.get(message.from_user.id)
    if await admins.is_admin(message.from_user.id):
        status = "👑 Admin — hamma imkoniyatlar bepul."
    elif user and user.is_premium:
        status = f"💎 Premium faol — <b>{fmt_date(user.premium_until)}</b> gacha.\nHamma imkoniyatlar cheksiz."
    else:
        left = user.free_files if user else 0
        status = f"🎁 Bepul fayllar: <b>{left}</b> ta qoldi."
    text = f"👤 <b>Hisobim</b>\n\n{status}"
    markup = None
    if not (user and user.is_premium):
        price = await premium_price(settings)
        text += "\n\n" + premium_offer(price)
        markup = premium_keyboard(price)
    await message.answer(text, reply_markup=markup)


@dp.message_handler(text=BTN_PREMIUM, state="*")
async def show_premium(message: types.Message, users: UserRepository, settings: SettingRepository):
    price = await premium_price(settings)
    text = premium_offer(price)
    user = await users.get(message.from_user.id)
    if user and user.is_premium:
        text += (
            f"\n\n✅ Sizda Premium faol: <b>{fmt_date(user.premium_until)}</b> gacha.\n"
            "Hozir to'lasangiz, muddat shu sanadan keyin qo'shiladi."
        )
    await message.answer(text, reply_markup=premium_keyboard(price))


@dp.message_handler(lambda m: m.text in LEGACY_BUTTONS, state="*")
async def legacy_button(message: types.Message):
    await message.answer(
        "🔄 Bot yangilandi! Tokenlar o'rniga endi <b>💎 Premium</b> — hamma narsa cheksiz.\n"
        "Yangi menyu 👇",
        reply_markup=main_menu,
    )
