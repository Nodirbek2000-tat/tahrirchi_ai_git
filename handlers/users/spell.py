"""Imlo tuzatish: tinish belgilari, katta harflar, tutuq, imlo xatolari.

Asosiy ish AI'siz qoidalar bilan; AI faqat shubhali murakkab gaplarga (juda tejamkor).
Kirillcha matn kirillda, lotincha matn lotinda tuzatiladi; rus/ingliz matnga tegilmaydi.
"""

import asyncio
import logging
import os
from collections import Counter

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from data import config
from db.models import TaskStatus
from db.repositories import (
    AdminRepository,
    SettingRepository,
    TaskRepository,
    UserRepository,
)
from handlers.users.common import FAILED_TEXT, cleanup, deny, num, receive_document
from keyboards.default import BTN_SPELL
from keyboards.inline.callbacks import spell_cb
from loader import ai, bot, dp
from services import access as acc
from services.converters import SCRIPT_STATS
from services.files.pdf_inplace import UnreadablePdfError
from services.files.translit_engine import flow_texts, scan_file, transliterate_file
from services.spelling import KIND_LABELS, SpellConverter
from services.spelling import ai as spell_ai
from services.spelling.converter import StyleStats, styles
from states import SpellState

logger = logging.getLogger(__name__)


def _keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("▶️ Tuzatishni boshlash", callback_data=spell_cb.new(action="start")),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=spell_cb.new(action="cancel")),
    )
    return kb


def _kinds_text(found: Counter) -> str:
    parts = [f"{KIND_LABELS.get(k, k)}: {num(v)}" for k, v in found.most_common() if v]
    return "\n".join("• " + p for p in parts)


def _base_converter(path: str) -> SpellConverter:
    """Hujjat tili (kirill qismlar o'zbekchami/ruscha) va uslubiga moslangan konverter."""
    stats = scan_file(path, SCRIPT_STATS) or Counter()
    quotes, dash = styles(scan_file(path, StyleStats()) or Counter())
    unknown_is_uz = stats.get("kirill_uz", 0) >= stats.get("kirill_ru", 0)
    return SpellConverter(unknown_is_uz=unknown_is_uz, quotes=quotes, dash=dash)


def _prescan(path: str) -> tuple[Counter, int]:
    conv = _base_converter(path)
    found = scan_file(path, conv) or Counter()
    candidates = spell_ai.select(flow_texts(path, conv), conv) if config.SPELL_AI else []
    return found, len(candidates)


@dp.message_handler(text=BTN_SPELL, state="*")
async def spell_menu(message: types.Message, state: FSMContext):
    cleanup((await state.get_data()).get("file_path"))
    await state.finish()
    await SpellState.waiting_file.set()
    await message.answer(
        "✍️ <b>Imlo tuzatish</b>\n\n"
        "Faylni yuboring (.docx, .xlsx, .pptx, .pdf, .txt).\n\n"
        "Tuzatiladi:\n"
        "• tinish belgilari ( . , ? ! : ; ) va bo'sh joylar\n"
        "• gap boshidagi va atoqli otlardagi katta harflar\n"
        "• oʻ, gʻ va tutuq belgisi ( ʼ ), qo'shtirnoq, tire\n"
        "• imlo xatolari (xozir → hozir, Узбекистон → Ўзбекистон)\n\n"
        "ℹ️ Kirillcha matn kirillda, lotincha matn lotinda tuzatiladi. Ruscha va inglizcha "
        "matnga tegilmaydi. Shrift, rang va dizayn o'zgarmaydi."
    )


@dp.message_handler(content_types=[types.ContentType.DOCUMENT], state=SpellState.waiting_file)
async def spell_receive_file(
    message: types.Message,
    users: UserRepository,
    admins: AdminRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    received = await receive_document(message, "imlo_")
    if received is None:
        return
    in_path, analysis, status_msg = received
    file_name = os.path.basename(in_path)
    try:
        found, ai_count = await asyncio.to_thread(_prescan, in_path)
    except UnreadablePdfError as exc:
        cleanup(in_path)
        await state.finish()
        await status_msg.edit_text(f"📄 <b>{file_name}</b>\n\n{exc.user_text}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Imlo tahlilida xato: %s", exc)
        cleanup(in_path)
        await status_msg.edit_text("❌ Faylni o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin.")
        return

    total = sum(found.values())
    if not total and not ai_count:
        cleanup(in_path)
        await state.finish()
        await status_msg.edit_text(
            f"📄 <b>{file_name}</b>\n\n🎉 Xato topilmadi — fayl toza!\n"
            "(Ruscha va inglizcha matn tekshirilmaydi.)\n🎁 Bepul fayllaringiz kamaymadi."
        )
        return

    head = f"📄 <b>{file_name}</b>\n📊 {analysis.unit_count} {analysis.unit_name}\n\n"
    if total:
        head += f"🔎 Topildi: <b>{num(total)}</b> ta tuzatish\n{_kinds_text(found)}\n"
    if ai_count:
        head += f"🤖 Chuqur tekshiriladi: <b>{num(ai_count)}</b> ta murakkab gap\n"
    head += "\n"

    access = await acc.check(users, admins, settings, message.from_user)
    if not access.allowed:
        cleanup(in_path)
        await state.finish()
        await deny(status_msg, head, settings)
        return

    await SpellState.confirm.set()
    await state.update_data(file_path=in_path, file_name=file_name, access=access.to_state())
    await status_msg.edit_text(
        head + acc.status_line(access) + "\n\nTuzatishni boshlaymizmi?", reply_markup=_keyboard()
    )


@dp.callback_query_handler(spell_cb.filter(), state=SpellState.confirm)
async def spell_start(
    call: types.CallbackQuery,
    callback_data: dict,
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

    if callback_data["action"] != "start":
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
    task = await tasks.create(call.from_user.id, f"[imlo] {file_name}", ext)
    out_name = f"imlo_{file_name}"
    out_path = os.path.join(os.path.dirname(file_path), out_name)
    await call.message.edit_text("⏳ Imlo tekshirilmoqda va tuzatilmoqda...")
    try:
        conv = await asyncio.to_thread(_base_converter, file_path)
        if config.SPELL_AI:
            candidates = await asyncio.to_thread(
                lambda: spell_ai.select(flow_texts(file_path, conv), conv)
            )
            if candidates:
                conv.ai_fixes = await spell_ai.ai_fixes(ai, candidates, conv.lexicon)
        report = await asyncio.to_thread(transliterate_file, file_path, out_path, conv)
        await tasks.set_status(task.id, TaskStatus.DONE)

        if not report.converted:
            await acc.refund(users, access)
            await call.message.edit_text(
                f"📄 <b>{file_name}</b>\n\n🎉 Xato topilmadi — fayl toza!\n"
                "🎁 Bepul fayllaringiz kamaymadi."
            )
            return

        caption = (
            f"✅ Tayyor! Imlo tuzatildi.\n\n"
            f"✏️ Tuzatildi: <b>{num(report.converted)}</b> ta\n{_kinds_text(report.found)}\n\n"
            f"{await acc.after_line(users, access)}"
        )
        if len(caption) > 1000:   # Telegram caption chegarasi
            caption = caption[:990] + "…"
        await bot.send_document(
            call.message.chat.id, types.InputFile(out_path, filename=out_name), caption=caption
        )
        await call.message.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Imlo tuzatishda xato: %s", exc)
        await acc.refund(users, access)
        await tasks.set_status(task.id, TaskStatus.FAILED)
        await call.message.edit_text(FAILED_TEXT)
    finally:
        cleanup(file_path)
        await state.finish()
