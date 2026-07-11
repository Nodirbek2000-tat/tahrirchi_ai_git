import asyncio
import logging
import os
import shutil
import tempfile

from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from db.models import TaskStatus
from db.repositories import AdminRepository, TaskRepository, UserRepository
from keyboards.inline import confirm_keyboard, packages_keyboard
from keyboards.inline.callbacks import process_cb
from loader import bot, corrector, dp
from services.files import (
    SUPPORTED_EXTENSIONS,
    UnsupportedFileError,
    get_processor,
)
from states import ProcessFileState

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # Telegram bot getFile chegarasi

UNSUPPORTED_TEXT = (
    "❌ Bu fayl turi qo'llab-quvvatlanmaydi.\n\n"
    "Qabul qilinadi: <b>.docx, .xlsx, .pptx, .pdf, .txt</b>"
)


def _cleanup(path: str | None) -> None:
    if not path:
        return
    folder = os.path.dirname(path)
    if folder and os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


@dp.message_handler(content_types=[types.ContentType.DOCUMENT], state="*")
async def receive_file(
    message: types.Message,
    users: UserRepository,
    admins: AdminRepository,
    state: FSMContext,
):
    document = message.document
    file_name = document.file_name or "fayl"
    ext = os.path.splitext(file_name)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        await message.answer(UNSUPPORTED_TEXT)
        return
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.answer("❗ Fayl hajmi 20 MB dan oshmasligi kerak.")
        return

    # Oldingi vaqtinchalik faylni tozalash
    old = await state.get_data()
    _cleanup(old.get("file_path"))
    await state.finish()

    status_msg = await message.answer("⏳ Fayl tekshirilmoqda...")

    tmp_dir = tempfile.mkdtemp(prefix="tahrir_")
    in_path = os.path.join(tmp_dir, file_name)
    try:
        tg_file = await bot.get_file(document.file_id)
        await bot.download_file(tg_file.file_path, in_path)
        processor = get_processor(file_name)
        analysis = await asyncio.to_thread(processor.analyze, in_path)
    except UnsupportedFileError:
        _cleanup(in_path)
        await status_msg.edit_text(UNSUPPORTED_TEXT)
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Faylni tahlil qilishda xato: %s", exc)
        _cleanup(in_path)
        await status_msg.edit_text("❌ Faylni o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin.")
        return

    if analysis.token_cost > config.MAX_TOKENS_PER_FILE:
        _cleanup(in_path)
        await status_msg.edit_text(
            f"❗ Fayl juda katta: <b>{analysis.unit_count} {analysis.unit_name}</b>.\n"
            f"Hozircha maksimal <b>{config.MAX_TOKENS_PER_FILE} sahifa</b> "
            f"qo'llab-quvvatlanadi. Iltimos, faylni bo'lib yuboring."
        )
        return

    is_admin = await admins.is_admin(message.from_user.id)
    user = await users.get(message.from_user.id)
    tokens = user.tokens if user else 0
    cost = analysis.token_cost

    await ProcessFileState.confirm.set()
    await state.update_data(
        file_path=in_path,
        file_name=file_name,
        token_cost=cost,
        is_admin=is_admin,
    )

    if is_admin:
        await status_msg.edit_text(
            f"📄 <b>{file_name}</b>\n"
            f"📊 {analysis.unit_count} {analysis.unit_name} aniqlandi.\n\n"
            f"👑 Admin — <b>bepul</b>.\n\n"
            f"Tahrirni boshlaymizmi?",
            reply_markup=confirm_keyboard(),
        )
        return

    if tokens < cost:
        _cleanup(in_path)
        await state.finish()
        await status_msg.edit_text(
            f"📄 <b>{file_name}</b>\n"
            f"📊 {analysis.unit_count} {analysis.unit_name} — <b>{cost} token</b> kerak.\n\n"
            f"💰 Balansingiz: <b>{tokens}</b> token — <b>yetarli emas</b>.\n"
            f"Quyidan token sotib oling:",
            reply_markup=packages_keyboard(),
        )
        return

    await status_msg.edit_text(
        f"📄 <b>{file_name}</b>\n"
        f"📊 {analysis.unit_count} {analysis.unit_name} aniqlandi.\n\n"
        f"🪙 Ketadi: <b>{cost} token</b>\n"
        f"💰 Balans: {tokens} → <b>{tokens - cost}</b> qoladi\n\n"
        f"Tahrirni boshlaymizmi?",
        reply_markup=confirm_keyboard(),
    )


@dp.callback_query_handler(
    process_cb.filter(action="cancel"), state=ProcessFileState.confirm
)
async def cancel_process(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    _cleanup(data.get("file_path"))
    await state.finish()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.answer()


@dp.callback_query_handler(
    process_cb.filter(action="start"), state=ProcessFileState.confirm
)
async def start_process(
    call: types.CallbackQuery,
    users: UserRepository,
    tasks: TaskRepository,
    state: FSMContext,
):
    await call.answer()
    data = await state.get_data()
    file_path = data.get("file_path")
    file_name = data.get("file_name")
    cost = data.get("token_cost")
    is_admin = data.get("is_admin", False)

    if not file_path or not os.path.exists(file_path):
        await state.finish()
        await call.message.edit_text("❗ Fayl muddati tugadi. Iltimos, qaytadan yuboring.")
        return

    # Adminlardan token yechilmaydi. Oddiy userdan atomik yechiladi.
    if not is_admin:
        ok = await users.deduct_tokens(call.from_user.id, cost)
        if not ok:
            _cleanup(file_path)
            await state.finish()
            await call.message.edit_text(
                "💰 Token yetarli emas. Quyidan sotib oling:",
                reply_markup=packages_keyboard(),
            )
            return

    ext = os.path.splitext(file_name)[1].lower()
    task = await tasks.create(call.from_user.id, file_name, ext, cost)
    out_path = os.path.join(os.path.dirname(file_path), f"tahrirlangan_{file_name}")

    await call.message.edit_text(
        "⏳ Tahrir qilinmoqda... Bu bir necha daqiqa vaqt olishi mumkin."
    )

    try:
        processor = get_processor(file_name)
        await processor.process(file_path, out_path, corrector)
        await tasks.set_status(task.id, TaskStatus.DONE)

        if is_admin:
            caption = "✅ Tayyor!\n👑 Admin — bepul."
        else:
            user = await users.get(call.from_user.id)
            caption = (
                f"✅ Tayyor!\n🪙 {cost} token ishlatildi.\n"
                f"💰 Qoldi: <b>{user.tokens}</b> token."
            )
        await bot.send_document(
            call.message.chat.id,
            types.InputFile(out_path, filename=f"tahrirlangan_{file_name}"),
            caption=caption,
        )
        await call.message.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tahrir qilishda xato: %s", exc)
        if not is_admin:
            await users.add_tokens(call.from_user.id, cost)  # tokenni qaytarish
        await tasks.set_status(task.id, TaskStatus.FAILED)
        await call.message.edit_text(
            "❌ Tahrir qilishda xatolik yuz berdi. Tokenlaringiz qaytarildi. "
            "Iltimos, keyinroq qayta urinib ko'ring."
        )
    finally:
        _cleanup(file_path)
        await state.finish()
