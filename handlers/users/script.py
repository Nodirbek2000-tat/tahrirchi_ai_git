"""Kirill <-> Lotin: faylning yozuvini almashtirish (tarjima emas, faqat harflar)."""

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
from keyboards.default import BTN_SCRIPT
from keyboards.inline.callbacks import script_cb
from keyboards.inline.script import DIRECTION_LABELS, direction_keyboard
from loader import bot, dp
from services import access as acc
from services.converters import SCRIPT_STATS, CyrToLatConverter, LatToCyrConverter
from services.files.pdf_inplace import UnreadablePdfError
from services.files.translit_engine import TranslitReport, scan_file, transliterate_file
from states import ScriptState

logger = logging.getLogger(__name__)

_OUT_PREFIX = {"cyr2lat": "lotin_", "cyr2new": "lotin_", "lat2cyr": "kirill_"}
_KIND_LABEL = {"kirill": "kirill harf", "lotin": "lotin harf"}


def _report_text(report: TranslitReport, ru_kept: int = 0) -> str:
    kept = f"\n🇷🇺 Ruscha matn tegilmadi: <b>{num(ru_kept)}</b> harf" if ru_kept else ""
    if not report.total_found:
        return "🔎 O'zgartiriladigan harf topilmadi." + kept
    kind = next(iter(report.found))
    return (
        f"🔎 Topildi: <b>{num(report.total_found)}</b> ta {_KIND_LABEL.get(kind, 'harf')}\n"
        f"✏️ O'zgartirildi: <b>{num(report.converted)}</b> ta\n"
        f"🔁 {report.passes} bosqichda tekshirildi · qolgan: <b>{report.remaining}</b>" + kept
    )


def _converter(direction: str, new_mode: bool | None, unknown_is_uz: bool):
    if direction in ("cyr2lat", "cyr2new"):
        return CyrToLatConverter(new=direction == "cyr2new", unknown_is_uz=unknown_is_uz)
    return LatToCyrConverter(new_mode=new_mode)


def _pct(part: int, total: int) -> int:
    return round(part * 100 / total) if total else 0


@dp.message_handler(text=BTN_SCRIPT, state="*")
async def script_menu(message: types.Message, state: FSMContext):
    cleanup((await state.get_data()).get("file_path"))
    await state.finish()
    await ScriptState.waiting_file.set()
    await message.answer(
        "🔤 <b>Kirill ↔ Lotin</b>\n\n"
        "Faylni yuboring (.docx, .xlsx, .pptx, .pdf, .txt).\n"
        "Bot yozuvni aniqlaydi, siz yo'nalishni tanlaysiz.\n\n"
        "ℹ️ Bu tarjima emas — faqat harflar almashtiriladi. "
        "Shrift, rang va joylashuv o'zgarmaydi."
    )


@dp.message_handler(content_types=[types.ContentType.DOCUMENT], state=ScriptState.waiting_file)
async def script_receive_file(
    message: types.Message,
    users: UserRepository,
    admins: AdminRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    received = await receive_document(message, "yozuv_")
    if received is None:
        return
    in_path, analysis, status_msg = received
    file_name = os.path.basename(in_path)
    try:
        stats = await asyncio.to_thread(scan_file, in_path, SCRIPT_STATS)
    except UnreadablePdfError as exc:
        cleanup(in_path)
        await state.finish()
        await status_msg.edit_text(f"📄 <b>{file_name}</b>\n\n{exc.user_text}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Yozuvni aniqlashda xato: %s", exc)
        cleanup(in_path)
        await status_msg.edit_text("❌ Faylni o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin.")
        return

    # Yozuv va til tarkibi. Har paragrafning tili alohida aniqlanadi; aniqlanmagan qisqa
    # paragraflar (nomlar, raqamli kataklar) hujjatdagi ko'pchilik tiliga qo'shiladi.
    uz, ru, unk = (stats.get(k, 0) for k in ("kirill_uz", "kirill_ru", "kirill_unk"))
    lat = stats.get("lotin", 0)
    unknown_is_uz = uz >= ru
    uz_cyr, ru_cyr = (uz + unk, ru) if unknown_is_uz else (uz, ru + unk)
    total = uz_cyr + ru_cyr + lat
    fully_russian = not uz_cyr and ru_cyr >= lat
    if not total or fully_russian:
        cleanup(in_path)
        await state.finish()
        reason = (
            "🇷🇺 Fayl to'liq <b>rus tilida</b> — o'zbekcha matn topilmadi.\n"
            "Rus tilidagi matn lotinga o'girilmaydi (bu tarjima emas)."
            if fully_russian and total else "🔎 Faylda harf topilmadi."
        )
        await status_msg.edit_text(
            f"📄 <b>{file_name}</b>\n\n{reason}\n🎁 Bepul fayllaringiz kamaymadi."
        )
        return

    parts = []
    if uz_cyr:
        parts.append(f"Kirill (o'zbekcha) <b>{_pct(uz_cyr, total)}%</b>")
    if ru_cyr:
        parts.append(f"Kirill (ruscha) <b>{_pct(ru_cyr, total)}%</b>")
    if lat:
        parts.append(f"Lotin <b>{_pct(lat, total)}%</b>")
    composition = "🔤 Yozuv: " + " · ".join(parts)
    if ru_cyr:
        composition += "\nℹ️ Ruscha qismlar o'zgarmaydi — faqat o'zbekcha matn o'giriladi."
    cyr_dirs = ["cyr2lat", "cyr2new"] if uz_cyr else []
    lat_dirs = ["lat2cyr"] if lat else []
    directions = cyr_dirs + lat_dirs if uz_cyr >= lat else lat_dirs + cyr_dirs
    new_mode = stats.get("yangi", 0) > stats.get("eski", 0)

    head = (
        f"📄 <b>{file_name}</b>\n"
        f"📊 {analysis.unit_count} {analysis.unit_name}\n"
        f"{composition}\n\n"
    )
    access = await acc.check(users, admins, settings, message.from_user)
    if not access.allowed:
        cleanup(in_path)
        await state.finish()
        await deny(status_msg, head, settings)
        return

    await ScriptState.choosing_direction.set()
    await state.update_data(
        file_path=in_path, file_name=file_name, access=access.to_state(),
        new_mode=new_mode, unknown_is_uz=unknown_is_uz, ru_kept=ru_cyr,
    )
    await status_msg.edit_text(
        head + acc.status_line(access) + "\n\n🔽 Qaysi tomonga o'giramiz?",
        reply_markup=direction_keyboard(directions),
    )


@dp.callback_query_handler(script_cb.filter(), state=ScriptState.choosing_direction)
async def script_convert(
    call: types.CallbackQuery,
    callback_data: dict,
    users: UserRepository,
    tasks: TaskRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    await call.answer()
    direction = callback_data["dir"]
    data = await state.get_data()
    file_path = data.get("file_path")
    file_name = data.get("file_name")
    access = acc.Access.from_state(data.get("access"), call.from_user.id)

    if direction == "cancel" or direction not in DIRECTION_LABELS:
        cleanup(file_path)
        await state.finish()
        await call.message.edit_text("❌ Bekor qilindi.")
        return

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
    task = await tasks.create(call.from_user.id, f"[{direction}] {file_name}", ext)
    out_name = _OUT_PREFIX[direction] + file_name
    out_path = os.path.join(os.path.dirname(file_path), out_name)
    conv = _converter(direction, data.get("new_mode"), data.get("unknown_is_uz", True))
    ru_kept = data.get("ru_kept", 0) if direction in ("cyr2lat", "cyr2new") else 0

    await call.message.edit_text(
        f"⏳ <b>{DIRECTION_LABELS[direction]}</b> — o'girilmoqda va qayta tekshirilmoqda..."
    )
    try:
        report = await asyncio.to_thread(transliterate_file, file_path, out_path, conv)
        await tasks.set_status(task.id, TaskStatus.DONE)
        caption = (
            f"✅ Tayyor! {DIRECTION_LABELS[direction]}\n\n{_report_text(report, ru_kept)}\n\n"
            f"{await acc.after_line(users, access)}"
        )
        await bot.send_document(
            call.message.chat.id, types.InputFile(out_path, filename=out_name), caption=caption
        )
        await call.message.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Kirill/lotin o'girishda xato: %s", exc)
        await acc.refund(users, access)
        await tasks.set_status(task.id, TaskStatus.FAILED)
        await call.message.edit_text(FAILED_TEXT)
    finally:
        cleanup(file_path)
        await state.finish()
