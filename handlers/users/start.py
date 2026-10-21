from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.builtin import CommandStart

from data import config
from db.repositories import SettingRepository, UserRepository
from keyboards.default import main_menu
from loader import dp

WELCOME = (
    "👋 Assalomu alaykum, <b>{name}</b>!\n\n"
    "Men <b>Tahrirchi AI</b> — hujjatlaringizni <b>yangi o'zbek lotin alifbosiga</b> "
    "o'giraman va tarjima qilaman.\n\n"
    "📎 <b>Qabul qilinadigan fayllar:</b>\n"
    "• Word (.docx)\n• Excel (.xlsx)\n• PowerPoint (.pptx)\n• PDF (.pdf)\n• Matn (.txt)\n\n"
    "🔤 sh→ş, ch→ç, gʻ→ğ, oʻ→ö — har bir so'z qayta-qayta tekshiriladi.\n"
    "Matn, uslub, rasm va tuzilma <b>o'zgarmaydi</b>.\n\n"
    "👇 Quyidagi tugmalardan birini tanlang:"
)


@dp.message_handler(CommandStart(), state="*")
async def bot_start(
    message: types.Message,
    users: UserRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    await state.finish()
    free_tokens = int(
        await settings.get_value(config.SETTING_FREE_TOKENS, config.FREE_TOKENS)
    )
    user, created = await users.get_or_create(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        free_tokens=free_tokens,
    )
    text = WELCOME.format(name=message.from_user.full_name)
    if created:
        text += f"\n\n🎁 Sizga <b>{free_tokens} ta bepul token</b> berildi!"
    await message.answer(text, reply_markup=main_menu)
