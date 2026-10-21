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
from keyboards.default import BTN_TRANSLATE
from keyboards.inline import packages_keyboard
from keyboards.inline.callbacks import translate_lang_cb
from keyboards.inline.translate import language_keyboard
from loader import ai, bot, dp
from services.files import SUPPORTED_EXTENSIONS, UnsupportedFileError, get_processor
from services.translation import (
    LANG_NAMES,
    Translator,
    build_sample,
    detect_language,
    target_languages,
)
from states import TranslateState

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024
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


@dp.message_handler(text=BTN_TRANSLATE, state="*")
async def translate_menu(message: types.Message, state: FSMContext):
    await state.finish()
    await TranslateState.waiting_file.set()
    await message.answer(
        "🌐 <b>Tarjima</b>\n\nTarjima qilinadigan faylni yuboring "
        "(.docx, .xlsx, .pptx, .pdf, .txt)."
    )


@dp.message_handler(
    content_types=[types.ContentType.DOCUMENT], state=TranslateState.waiting_file
)
async def translate_receive_file(
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

    tmp_dir = tempfile.mkdtemp(prefix="tarjima_")
    in_path = os.path.join(tmp_dir, file_name)
    try:
        tg_file = await bot.get_file(document.file_id)
        await bot.download_file(tg_file.file_path, in_path)
        processor = get_processor(file_name)
        analysis = await asyncio.to_thread(processor.analyze, in_path)
        _, segments = await asyncio.to_thread(processor._extract, in_path)
    except UnsupportedFileError:
        _cleanup(in_path)
        await status_msg.edit_text(UNSUPPORTED_TEXT)
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tarjima uchun faylni o'qishda xato: %s", exc)
        _cleanup(in_path)
        await status_msg.edit_text("❌ Faylni o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin.")
        return

    if analysis.token_cost > config.MAX_TRANSLATE_TOKENS:
        _cleanup(in_path)
        await state.finish()
        await status_msg.edit_text(
            f"❗ Fayl juda katta: <b>{analysis.unit_count} {analysis.unit_name}</b>.\n"
            f"Tarjima uchun maksimal <b>{config.MAX_TRANSLATE_TOKENS} sahifa</b>."
        )
        return

    # Manba tilini AI bilan BUTUN matndan aniqlash (foizlar bilan)
    await status_msg.edit_text("🔎 Til aniqlanmoqda...")
    sample = build_sample(segments)
    stats = await ai.detect_language_stats(sample)
    if not stats:
        src = detect_language(sample)  # zaxira (heuristika)
        stats = {src: 100}
    source = max(stats, key=stats.get)
    targets = target_languages(source)
    ordered = sorted(stats.items(), key=lambda kv: -kv[1])
    breakdown = " · ".join(f"{LANG_NAMES.get(k, k)} {v}%" for k, v in ordered if v > 0)

    is_admin = await admins.is_admin(message.from_user.id)
    user = await users.get(message.from_user.id)
    tokens = user.tokens if user else 0
    cost = analysis.token_cost

    await TranslateState.choosing_language.set()
    await state.update_data(
        file_path=in_path, file_name=file_name, token_cost=cost, is_admin=is_admin
    )

    head = (
        f"📄 <b>{file_name}</b>\n"
        f"📊 {analysis.unit_count} {analysis.unit_name}\n"
        f"🌐 Til tarkibi: {breakdown}\n"
        f"🏆 Asosiy til: <b>{LANG_NAMES.get(source, source)}</b>\n\n"
    )
    if is_admin:
        head += "👑 Admin — <b>bepul</b>.\n\n"
    elif tokens < cost:
        _cleanup(in_path)
        await state.finish()
        token_price = int(
            await settings.get_value(config.SETTING_TOKEN_PRICE, config.TOKEN_PRICE)
        )
        await status_msg.edit_text(
            head
            + f"🪙 Kerak: <b>{cost} token</b> · Balans: <b>{tokens}</b> — yetarli emas.\n"
            "Quyidan token sotib oling:",
            reply_markup=packages_keyboard(token_price),
        )
        return
    else:
        head += f"🪙 Tarjima: <b>{cost} token</b> · Balans: {tokens} → <b>{tokens - cost}</b>\n\n"

    await status_msg.edit_text(
        head + "🔽 Qaysi tilga tarjima qilamiz?",
        reply_markup=language_keyboard(targets),
    )


@dp.callback_query_handler(
    translate_lang_cb.filter(), state=TranslateState.choosing_language
)
async def translate_do(
    call: types.CallbackQuery,
    callback_data: dict,
    users: UserRepository,
    tasks: TaskRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    await call.answer()
    lang = callback_data["lang"]
    data = await state.get_data()
    file_path = data.get("file_path")
    file_name = data.get("file_name")
    cost = data.get("token_cost")
    is_admin = data.get("is_admin", False)

    if lang == "cancel":
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
            token_price = int(
                await settings.get_value(config.SETTING_TOKEN_PRICE, config.TOKEN_PRICE)
            )
            await call.message.edit_text(
                "💰 Token yetarli emas. Quyidan sotib oling:",
                reply_markup=packages_keyboard(token_price),
            )
            return

    ext = os.path.splitext(file_name)[1].lower()
    task = await tasks.create(call.from_user.id, f"[tr:{lang}] {file_name}", ext, cost)
    out_name = f"tarjima_{lang}_{file_name}"
    out_path = os.path.join(os.path.dirname(file_path), out_name)

    await call.message.edit_text(
        f"⏳ <b>{LANG_NAMES.get(lang, lang)}</b> tiliga tarjima qilinmoqda... "
        "Bu bir necha daqiqa vaqt olishi mumkin."
    )

    try:
        processor = get_processor(file_name)
        translator = Translator(ai, lang)
        await processor.process(file_path, out_path, translator)
        await tasks.set_status(task.id, TaskStatus.DONE)

        if is_admin:
            caption = f"✅ Tayyor! {LANG_NAMES.get(lang, lang)} tiliga tarjima.\n👑 Admin — bepul."
        else:
            user = await users.get(call.from_user.id)
            caption = (
                f"✅ Tayyor! {LANG_NAMES.get(lang, lang)} tiliga tarjima.\n"
                f"🪙 {cost} token ishlatildi. 💰 Qoldi: <b>{user.tokens}</b> token."
            )
        await bot.send_document(
            call.message.chat.id,
            types.InputFile(out_path, filename=out_name),
            caption=caption,
        )
        await call.message.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tarjima qilishda xato: %s", exc)
        if not is_admin:
            await users.add_tokens(call.from_user.id, cost)
        await tasks.set_status(task.id, TaskStatus.FAILED)
        await call.message.edit_text(
            "❌ Tarjima qilishda xatolik yuz berdi. Tokenlaringiz qaytarildi. "
            "Iltimos, keyinroq qayta urinib ko'ring."
        )
    finally:
        _cleanup(file_path)
        await state.finish()
