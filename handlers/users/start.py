from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.builtin import CommandStart

from data import config
from db.repositories import UserRepository
from keyboards.default import main_menu
from loader import dp

WELCOME = (
    "👋 Assalomu alaykum, <b>{name}</b>!\n\n"
    "Men <b>Tahrirchi AI</b> — hujjatlaringizni <b>yangi o'zbek lotin alifbosiga</b> "
    "o'giraman va imloviy xatolarni to'g'irlab beraman.\n\n"
    "📎 <b>Qabul qilinadigan fayllar:</b>\n"
    "• Word (.docx)\n• Excel (.xlsx)\n• PowerPoint (.pptx)\n• PDF (.pdf)\n• Matn (.txt)\n\n"
    "🔤 sh→ş, ch→ç, gʻ→ğ, oʻ→ö + imlo tuzatish.\n"
    "Matn, uslub, rasm va tuzilma <b>o'zgarmaydi</b>.\n\n"
    "👇 Quyidagi tugmalardan birini tanlang:"
)


@dp.message_handler(CommandStart(), state="*")
async def bot_start(message: types.Message, users: UserRepository, state: FSMContext):
    await state.finish()
    user, created = await users.get_or_create(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )
    text = WELCOME.format(name=message.from_user.full_name)
    if created:
        text += f"\n\n🎁 Sizga <b>{config.FREE_TOKENS} ta bepul token</b> berildi!"
    await message.answer(text, reply_markup=main_menu)
