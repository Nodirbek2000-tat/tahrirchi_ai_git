"""Yangi alifbo: sh→ş, ch→ç, gʻ→ğ, oʻ→ö (istalgan bo'limdan tashqari yuborilgan fayl)."""

import asyncio
import logging
import os

from aiogram import types
from aiogram.dispatcher import FSMContext

from db.models import TaskStatus
from db.repositories import (
    AdminRepository,
    SettingRepository,
    TaskRepository,
    UserRepository,
)
from handlers.users.common import FAILED_TEXT, cleanup, deny, num, receive_document
from keyboards.inline import confirm_keyboard
from keyboards.inline.callbacks import process_cb
from loader import bot, dp
from services import access as acc
from services.files.pdf_inplace import UnreadablePdfError
from services.files.translit_engine import TranslitReport, scan_file, transliterate_file
from services.transliteration import KINDS
from states import ProcessFileState

logger = logging.getLogger(__name__)


def _kinds_text(found) -> str:
    return " · ".join(f"{kind}: {num(found[kind])}" for kind in KINDS if found.get(kind))


def _report_text(report: TranslitReport) -> str:
    if not report.total_found:
        return "🔎 O'zgartiriladigan harf topilmadi."
    return (
        f"🔎 Topildi: <b>{num(report.total_found)}</b> ta ({_kinds_text(report.found)})\n"
        f"✏️ O'zgartirildi: <b>{num(report.converted)}</b> ta\n"
        f"🔁 {report.passes} bosqichda tekshirildi · qolgan: <b>{report.remaining}</b>"
    )


@dp.message_handler(content_types=[types.ContentType.DOCUMENT], state="*")
async def receive_file(
    message: types.Message,
    users: UserRepository,
    admins: AdminRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    # Oldingi vaqtinchalik faylni tozalash
    cleanup((await state.get_data()).get("file_path"))
    await state.finish()

    received = await receive_document(message, "tahrir_")
    if received is None:
        return
    in_path, analysis, status_msg = received
    file_name = os.path.basename(in_path)

    # 1-tahlil: faylda nechta o'giriladigan harf bor
    found = None
    try:
        found = await asyncio.to_thread(scan_file, in_path)
    except UnreadablePdfError as exc:
        cleanup(in_path)
        await status_msg.edit_text(f"📄 <b>{file_name}</b>\n\n{exc.user_text}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("Oldindan skan qilib bo'lmadi: %s", exc)
    if found is not None and not sum(found.values()):
        cleanup(in_path)
        await status_msg.edit_text(
            f"📄 <b>{file_name}</b>\n\n"
            "🔎 Faylda sh, ch, gʻ, oʻ harflari topilmadi — o'zgartirish shart emas.\n"
            "🎁 Bepul fayllaringiz kamaymadi."
        )
        return

    head = f"📄 <b>{file_name}</b>\n📊 {analysis.unit_count} {analysis.unit_name}\n"
    if found:
        head += f"🔎 Topildi: <b>{num(sum(found.values()))}</b> ta harf ({_kinds_text(found)})\n"
    head += "\n"

    access = await acc.check(users, admins, settings, message.from_user)
    if not access.allowed:
        cleanup(in_path)
        await deny(status_msg, head, settings)
        return

    await ProcessFileState.confirm.set()
    await state.update_data(file_path=in_path, file_name=file_name, access=access.to_state())
    await status_msg.edit_text(
        head + acc.status_line(access) + "\n\nTahrirni boshlaymizmi?",
        reply_markup=confirm_keyboard(),
    )


@dp.callback_query_handler(process_cb.filter(action="cancel"), state=ProcessFileState.confirm)
async def cancel_process(call: types.CallbackQuery, state: FSMContext):
    cleanup((await state.get_data()).get("file_path"))
    await state.finish()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.answer()


@dp.callback_query_handler(process_cb.filter(action="start"), state=ProcessFileState.confirm)
async def start_process(
    call: types.CallbackQuery,
    users: UserRepository,
    tasks: TaskRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    await call.answer()
    data = await state.get_data()
    file_path = data.get("file_path")
    file_name = data.get("file_name")
    access = acc.Access.from_state(data.get("access"), call.from_user.id)

    if not file_path or not os.path.exists(file_path):
        await state.finish()
        await call.message.edit_text("❗ Fayl muddati tugadi. Iltimos, qaytadan yuboring.")
        return

    if not await acc.consume(users, access):
        cleanup(file_path)
        await state.finish()
        await deny(call.message, "", settings)
        return

    ext = os.path.splitext(file_name)[1].lower()
    task = await tasks.create(call.from_user.id, file_name, ext)
    out_name = f"tahrirlangan_{file_name}"
    out_path = os.path.join(os.path.dirname(file_path), out_name)

    await call.message.edit_text("⏳ Harflar o'girilmoqda va qayta tekshirilmoqda...")
    try:
        report = await asyncio.to_thread(transliterate_file, file_path, out_path)
        await tasks.set_status(task.id, TaskStatus.DONE)
        caption = f"✅ Tayyor!\n\n{_report_text(report)}\n\n{await acc.after_line(users, access)}"
        await bot.send_document(
            call.message.chat.id, types.InputFile(out_path, filename=out_name), caption=caption
        )
        await call.message.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tahrir qilishda xato: %s", exc)
        await acc.refund(users, access)
        await tasks.set_status(task.id, TaskStatus.FAILED)
        await call.message.edit_text(FAILED_TEXT)
    finally:
        cleanup(file_path)
        await state.finish()
