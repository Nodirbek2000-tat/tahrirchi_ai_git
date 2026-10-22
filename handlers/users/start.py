from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.builtin import CommandStart

from db.repositories import SettingRepository, UserRepository
from keyboards.default import main_menu
from loader import dp
from services.access import free_files_default

WELCOME = (
    "👋 Assalomu alaykum, <b>{name}</b>!\n\n"
    "Men <b>Tahrirchi AI</b> — hujjatlaringizni tahrirlayman:\n\n"
    "🔤 <b>Yangi alifbo:</b> sh→ş, ch→ç, gʻ→ğ, oʻ→ö\n"
    "✍️ <b>Imlo:</b> tinish belgilari, katta harflar, imlo xatolari\n"
    "🔁 <b>Kirill ↔ Lotin:</b> yozuvni almashtirish\n"
    "💬 <b>Matnni o'girish:</b> matn yuboring — darhol yangi alifboda qaytaraman\n\n"
    "📎 Word, Excel, PowerPoint, PDF, TXT fayllar.\n"
    "Shrift, rang, rasm va dizayn <b>o'zgarmaydi</b>.\n\n"
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
    free_files = await free_files_default(settings)
    user, created = await users.get_or_create(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        free_files=free_files,
    )
    text = WELCOME.format(name=message.from_user.full_name)
    if created and free_files:
        text += (
            f"\n\n🎁 Sizga <b>{free_files} ta faylni bepul</b> tahrirlash va "
            f"<b>{user.free_texts} ta matnni bepul</b> o'girish imkoniyati berildi!"
        )
    await message.answer(text, reply_markup=main_menu)
