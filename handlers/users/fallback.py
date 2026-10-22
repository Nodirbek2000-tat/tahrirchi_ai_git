from aiogram import types

from loader import dp


@dp.message_handler(state="*", content_types=types.ContentType.ANY)
async def fallback(message: types.Message):
    await message.answer(
        "📄 Tahrir qilish uchun menga <b>fayl</b> yuboring "
        "(.docx, .xlsx, .pptx, .pdf, .txt),\n"
        "💬 yoki <b>matn</b> yozing — yangi alifboga o'girib beraman,\n"
        "yoki pastdagi menyudan foydalaning."
    )
