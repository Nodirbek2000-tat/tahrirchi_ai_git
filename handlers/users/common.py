"""Fayl bilan ishlovchi bo'limlar (alifbo, kirill↔lotin, imlo) uchun umumiy qism.

Bu modulda handler yo'q — faqat yordamchi funksiyalar.
"""

import asyncio
import logging
import os
import shutil
import tempfile

from aiogram import types

from data import config
from db.repositories import SettingRepository
from keyboards.inline import premium_keyboard
from loader import bot
from services.access import NO_ACCESS, premium_offer, premium_price
from services.files import SUPPORTED_EXTENSIONS, FileAnalysis, UnsupportedFileError, get_processor

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # Telegram bot getFile chegarasi
UNSUPPORTED_TEXT = (
    "❌ Bu fayl turi qo'llab-quvvatlanmaydi.\n\n"
    "Qabul qilinadi: <b>.docx, .xlsx, .pptx, .pdf, .txt</b>"
)
FAILED_TEXT = (
    "❌ Tahrirlashda xatolik yuz berdi. Bepul faylingiz qaytarildi.\n"
    "Iltimos, keyinroq qayta urinib ko'ring."
)


def cleanup(path: str | None) -> None:
    if not path:
        return
    folder = os.path.dirname(path)
    if folder and os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


def num(value: int) -> str:
    return f"{value:,}".replace(",", " ")


async def receive_document(
    message: types.Message, prefix: str
) -> tuple[str, FileAnalysis, types.Message] | None:
    """Faylni tekshiradi va yuklab oladi. Muammo bo'lsa userga aytadi va None qaytaradi."""
    document = message.document
    file_name = document.file_name or "fayl"
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        await message.answer(UNSUPPORTED_TEXT)
        return None
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.answer("❗ Fayl hajmi 20 MB dan oshmasligi kerak.")
        return None

    status_msg = await message.answer("⏳ Fayl tekshirilmoqda...")
    in_path = os.path.join(tempfile.mkdtemp(prefix=prefix), file_name)
    try:
        tg_file = await bot.get_file(document.file_id)
        await bot.download_file(tg_file.file_path, in_path)
        analysis = await asyncio.to_thread(get_processor(file_name).analyze, in_path)
    except UnsupportedFileError:
        cleanup(in_path)
        await status_msg.edit_text(UNSUPPORTED_TEXT)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Faylni o'qishda xato: %s", exc)
        cleanup(in_path)
        await status_msg.edit_text("❌ Faylni o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin.")
        return None

    if analysis.pages > config.MAX_PAGES_PER_FILE:
        cleanup(in_path)
        await status_msg.edit_text(
            f"❗ Fayl juda katta: <b>{analysis.unit_count} {analysis.unit_name}</b>.\n"
            f"Maksimal <b>{config.MAX_PAGES_PER_FILE} sahifa</b>. Iltimos, faylni bo'lib yuboring."
        )
        return None
    return in_path, analysis, status_msg


async def deny(status_msg: types.Message, head: str, settings: SettingRepository) -> None:
    """Bepul fayllari tugagan userga premium taklifi."""
    price = await premium_price(settings)
    await status_msg.edit_text(
        head + f"{NO_ACCESS}\n\n" + premium_offer(price),
        reply_markup=premium_keyboard(price),
    )
