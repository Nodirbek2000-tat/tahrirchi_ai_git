import asyncio
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from db.repositories import UserRepository
from keyboards.inline.admin_panel import admin_menu
from keyboards.inline.broadcast import ad_markup, confirm_broadcast_keyboard
from keyboards.inline.callbacks import broadcast_cb
from loader import bot, dp
from utils.misc.filters import not_command
from services.broadcast import run_broadcast
from states import BroadcastState

logger = logging.getLogger(__name__)

_ALL_STATES = [
    BroadcastState.text,
    BroadcastState.photo,
    BroadcastState.button_name,
    BroadcastState.button_url,
    BroadcastState.confirm,
]


async def _show_preview(chat_id: int, state: FSMContext):
    data = await state.get_data()
    markup = ad_markup(data.get("btn_name"), data.get("btn_url"))
    if data.get("photo"):
        await bot.send_photo(chat_id, data["photo"], caption=data["text"], reply_markup=markup)
    else:
        await bot.send_message(chat_id, data["text"], reply_markup=markup)
    await BroadcastState.confirm.set()
    await bot.send_message(
        chat_id,
        "👆 Reklama shu ko'rinishda yuboriladi. Tasdiqlaysizmi?",
        reply_markup=confirm_broadcast_keyboard(),
    )


# --- Bekor qilish (istalgan qadamda) ---
@dp.message_handler(commands=["cancel"], state=_ALL_STATES)
async def broadcast_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Reklama bekor qilindi.", reply_markup=admin_menu())


# --- 1) Matn ---
@dp.message_handler(not_command, state=BroadcastState.text, content_types=types.ContentType.ANY)
async def broadcast_text(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Iltimos, reklama matnini yuboring.")
        return
    await state.update_data(text=message.html_text)
    await BroadcastState.photo.set()
    await message.answer("2-qadam: Reklama <b>rasmini</b> yuboring yoki /skip.")


# --- 2) Rasm (ixtiyoriy) ---
@dp.message_handler(commands=["skip"], state=BroadcastState.photo)
async def broadcast_photo_skip(message: types.Message, state: FSMContext):
    await BroadcastState.button_name.set()
    await message.answer("3-qadam: <b>Tugma nomini</b> yuboring yoki /skip.")


@dp.message_handler(not_command, state=BroadcastState.photo, content_types=types.ContentType.ANY)
async def broadcast_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("❗ Rasm yuboring yoki /skip.")
        return
    await state.update_data(photo=message.photo[-1].file_id)
    await BroadcastState.button_name.set()
    await message.answer("3-qadam: <b>Tugma nomini</b> yuboring yoki /skip.")


# --- 3) Tugma nomi (ixtiyoriy) ---
@dp.message_handler(commands=["skip"], state=BroadcastState.button_name)
async def broadcast_name_skip(message: types.Message, state: FSMContext):
    await _show_preview(message.chat.id, state)


@dp.message_handler(not_command, state=BroadcastState.button_name, content_types=types.ContentType.ANY)
async def broadcast_button_name(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Tugma nomini matn ko'rinishida yuboring yoki /skip.")
        return
    await state.update_data(btn_name=message.text.strip())
    await BroadcastState.button_url.set()
    await message.answer(
        "4-qadam: Tugma <b>linkini</b> yuboring (masalan: https://t.me/kanal)."
    )


# --- 4) Tugma linki ---
@dp.message_handler(not_command, state=BroadcastState.button_url, content_types=types.ContentType.ANY)
async def broadcast_button_url(message: types.Message, state: FSMContext):
    url = (message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("t.me/")):
        await message.answer("❗ To'g'ri link yuboring (https://... yoki t.me/...).")
        return
    if url.startswith("t.me/"):
        url = "https://" + url
    await state.update_data(btn_url=url)
    await _show_preview(message.chat.id, state)


# --- 5) Tasdiqlash / yuborish ---
@dp.callback_query_handler(broadcast_cb.filter(), state=BroadcastState.confirm)
async def broadcast_finish(
    call: types.CallbackQuery,
    callback_data: dict,
    users: UserRepository,
    state: FSMContext,
):
    await call.answer()
    if callback_data["action"] == "cancel":
        await state.finish()
        await call.message.edit_text("❌ Reklama bekor qilindi.")
        return

    data = await state.get_data()
    await state.finish()

    user_ids = await users.all_ids()
    await call.message.edit_text(
        f"📤 Yuborish boshlandi... (<b>{len(user_ids)}</b> ta foydalanuvchi).\n"
        "Yakunlanganda hisobot keladi."
    )

    admin_id = call.from_user.id
    text = data.get("text", "")
    photo = data.get("photo")
    btn_name = data.get("btn_name")
    btn_url = data.get("btn_url")

    async def job():
        sent, failed = await run_broadcast(bot, user_ids, text, photo, btn_name, btn_url)
        try:
            await bot.send_message(
                admin_id,
                f"✅ Reklama yakunlandi.\n📤 Yuborildi: <b>{sent}</b>\n"
                f"❌ Yuborilmadi: <b>{failed}</b>",
            )
        except Exception:  # noqa: BLE001
            pass

    asyncio.create_task(job())
