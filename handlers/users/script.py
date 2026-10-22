"""Kirill <-> Lotin: faylning yozuvini almashtirish (tarjima emas, faqat harflar)."""

import asyncio
import logging
import os
import shutil
import tempfile

from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from db.models import TaskStatus
from db.repositories import (
    AdminRepository,
    SettingRepository,
    TaskRepository,
    UserRepository,
)
from keyboards.default import BTN_SCRIPT
from keyboards.inline import packages_keyboard
from keyboards.inline.callbacks import script_cb
from keyboards.inline.script import DIRECTION_LABELS, direction_keyboard
from loader import bot, dp
from services.converters import SCRIPT_STATS, CyrToLatConverter, LatToCyrConverter
from services.files import SUPPORTED_EXTENSIONS, UnsupportedFileError, get_processor
from services.files.pdf_inplace import UnreadablePdfError
from services.files.translit_engine import TranslitReport, scan_file, transliterate_file
from states import ScriptState

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024
UNSUPPORTED_TEXT = (
    "❌ Bu fayl turi qo'llab-quvvatlanmaydi.\n\n"
    "Qabul qilinadi: <b>.docx, .xlsx, .pptx, .pdf, .txt</b>"
)
_OUT_PREFIX = {"cyr2lat": "lotin_", "cyr2new": "lotin_", "lat2cyr": "kirill_"}
_KIND_LABEL = {"kirill": "kirill harf", "lotin": "lotin harf"}


def _cleanup(path: str | None) -> None:
    if not path:
        return
    folder = os.path.dirname(path)
    if folder and os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


def _num(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _report_text(report: TranslitReport, ru_kept: int = 0) -> str:
    kept = f"\n🇷🇺 Ruscha matn tegilmadi: <b>{_num(ru_kept)}</b> harf" if ru_kept else ""
    if not report.total_found:
        return "🔎 O'zgartiriladigan harf topilmadi." + kept
    kind = next(iter(report.found))
    return (
        f"🔎 Topildi: <b>{_num(report.total_found)}</b> ta {_KIND_LABEL.get(kind, 'harf')}\n"
        f"✏️ O'zgartirildi: <b>{_num(report.converted)}</b> ta\n"
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
    document = message.document
    file_name = document.file_name or "fayl"
    ext = os.path.splitext(file_name)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        await message.answer(UNSUPPORTED_TEXT)
        return
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.answer("❗ Fayl hajmi 20 MB dan oshmasligi kerak.")
        return

    status_msg = await message.answer("⏳ Fayl tekshirilmoqda...")
    tmp_dir = tempfile.mkdtemp(prefix="yozuv_")
    in_path = os.path.join(tmp_dir, file_name)
    try:
        tg_file = await bot.get_file(document.file_id)
        await bot.download_file(tg_file.file_path, in_path)
        analysis = await asyncio.to_thread(get_processor(file_name).analyze, in_path)
        stats = await asyncio.to_thread(scan_file, in_path, SCRIPT_STATS)
    except UnsupportedFileError:
        _cleanup(in_path)
        await status_msg.edit_text(UNSUPPORTED_TEXT)
        return
    except UnreadablePdfError as exc:
        _cleanup(in_path)
        await state.finish()
        await status_msg.edit_text(f"📄 <b>{file_name}</b>\n\n{exc.user_text}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Faylni o'qishda xato: %s", exc)
        _cleanup(in_path)
        await status_msg.edit_text("❌ Faylni o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin.")
        return

    if analysis.token_cost > config.MAX_TOKENS_PER_FILE:
        _cleanup(in_path)
        await state.finish()
        await status_msg.edit_text(
            f"❗ Fayl juda katta: <b>{analysis.unit_count} {analysis.unit_name}</b>.\n"
            f"Maksimal <b>{config.MAX_TOKENS_PER_FILE} sahifa</b>."
        )
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
        _cleanup(in_path)
        await state.finish()
        reason = (
            "🇷🇺 Fayl to'liq <b>rus tilida</b> — o'zbekcha matn topilmadi.\n"
            "Rus tilidagi matn lotinga o'girilmaydi (bu tarjima emas)."
            if fully_russian and total else "🔎 Faylda harf topilmadi."
        )
        await status_msg.edit_text(f"📄 <b>{file_name}</b>\n\n{reason}\n🪙 Token yechilmadi.")
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

    is_admin = await admins.is_admin(message.from_user.id)
    user = await users.get(message.from_user.id)
    tokens = user.tokens if user else 0
    cost = analysis.token_cost
    head = (
        f"📄 <b>{file_name}</b>\n"
        f"📊 {analysis.unit_count} {analysis.unit_name}\n"
        f"{composition}\n\n"
    )

    if not is_admin and tokens < cost:
        _cleanup(in_path)
        await state.finish()
        token_price = int(await settings.get_value(config.SETTING_TOKEN_PRICE, config.TOKEN_PRICE))
        await status_msg.edit_text(
            head + f"🪙 Kerak: <b>{cost} token</b> · Balans: <b>{tokens}</b> — yetarli emas.\n"
            "Quyidan token sotib oling:",
            reply_markup=packages_keyboard(token_price),
        )
        return

    await ScriptState.choosing_direction.set()
    await state.update_data(
        file_path=in_path, file_name=file_name, token_cost=cost,
        is_admin=is_admin, new_mode=new_mode, unknown_is_uz=unknown_is_uz, ru_kept=ru_cyr,
    )
    price_line = (
        "👑 Admin — <b>bepul</b>.\n\n" if is_admin
        else f"🪙 Ketadi: <b>{cost} token</b> · Balans: {tokens} → <b>{tokens - cost}</b>\n\n"
    )
    await status_msg.edit_text(
        head + price_line + "🔽 Qaysi tomonga o'giramiz?",
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
    cost = data.get("token_cost")
    is_admin = data.get("is_admin", False)

    if direction == "cancel" or direction not in DIRECTION_LABELS:
        _cleanup(file_path)
        await state.finish()
        await call.message.edit_text("❌ Bekor qilindi.")
        return

    if not file_path or not os.path.exists(file_path):
        await state.finish()
        await call.message.edit_text("❗ Fayl muddati tugadi. Iltimos, qaytadan yuboring.")
        return

    if not is_admin:
        ok = await users.deduct_tokens(call.from_user.id, cost)
        if not ok:
            _cleanup(file_path)
            await state.finish()
            token_price = int(await settings.get_value(config.SETTING_TOKEN_PRICE, config.TOKEN_PRICE))
            await call.message.edit_text(
                "💰 Token yetarli emas. Quyidan sotib oling:",
                reply_markup=packages_keyboard(token_price),
            )
            return

    ext = os.path.splitext(file_name)[1].lower()
    task = await tasks.create(call.from_user.id, f"[{direction}] {file_name}", ext, cost)
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

        summary = _report_text(report, ru_kept)
        if is_admin:
            caption = f"✅ Tayyor! {DIRECTION_LABELS[direction]}\n\n{summary}\n\n👑 Admin — bepul."
        else:
            user = await users.get(call.from_user.id)
            caption = (
                f"✅ Tayyor! {DIRECTION_LABELS[direction]}\n\n{summary}\n\n"
                f"🪙 {cost} token ishlatildi · 💰 Qoldi: <b>{user.tokens}</b> token."
            )
        await bot.send_document(
            call.message.chat.id, types.InputFile(out_path, filename=out_name), caption=caption
        )
        await call.message.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Kirill/lotin o'girishda xato: %s", exc)
        if not is_admin:
            await users.add_tokens(call.from_user.id, cost)
        await tasks.set_status(task.id, TaskStatus.FAILED)
        await call.message.edit_text(
            "❌ O'girishda xatolik yuz berdi. Tokenlaringiz qaytarildi. "
            "Iltimos, keyinroq qayta urinib ko'ring."
        )
    finally:
        _cleanup(file_path)
        await state.finish()
