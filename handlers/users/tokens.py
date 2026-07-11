import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from db.repositories import PaymentRepository
from keyboards.inline import receipt_keyboard, review_keyboard
from keyboards.inline.callbacks import buy_cb, receipt_cb
from loader import bot, dp
from states import BuyTokenState

logger = logging.getLogger(__name__)


@dp.callback_query_handler(buy_cb.filter(), state="*")
async def choose_package(
    call: types.CallbackQuery,
    callback_data: dict,
    payments: PaymentRepository,
    state: FSMContext,
):
    package = callback_data["package"]
    if package not in config.TOKEN_PACKAGES:
        await call.answer("Noto'g'ri paket", show_alert=True)
        return
    tokens, amount = config.TOKEN_PACKAGES[package]

    payment = await payments.create(
        user_id=call.from_user.id, package=package, tokens=tokens, amount=amount
    )
    await BuyTokenState.waiting_receipt.set()
    await state.update_data(payment_id=payment.id)

    text = (
        f"💳 <b>To'lov</b>\n\n"
        f"📦 Paket: <b>{tokens} token</b>\n"
        f"💵 Summa: <b>{amount:,} so'm</b>\n\n".replace(",", " ")
        + f"Quyidagi kartaga o'tkazing:\n\n"
        f"<code>{config.CARD_NUMBER}</code>\n"
        f"👤 {config.CARD_HOLDER}\n\n"
        f"To'lovdan so'ng <b>«✅ Chek yuborish»</b> tugmasini bosing va "
        f"chek rasmini yuboring."
    )
    await call.message.edit_text(text, reply_markup=receipt_keyboard(payment.id))
    await call.answer()


@dp.callback_query_handler(
    receipt_cb.filter(), state=BuyTokenState.waiting_receipt
)
async def ask_receipt(call: types.CallbackQuery):
    await call.message.answer(
        "🧾 Iltimos, to'lov chekining <b>rasmini</b> yoki faylini yuboring."
    )
    await call.answer()


@dp.message_handler(
    content_types=[types.ContentType.PHOTO, types.ContentType.DOCUMENT],
    state=BuyTokenState.waiting_receipt,
)
async def receive_receipt(
    message: types.Message, payments: PaymentRepository, state: FSMContext
):
    data = await state.get_data()
    payment_id = data.get("payment_id")
    payment = await payments.get(payment_id) if payment_id else None
    if not payment:
        await state.finish()
        await message.answer("❗ To'lov topilmadi. Qaytadan «🪙 Token olish» ni bosing.")
        return

    is_photo = message.content_type == types.ContentType.PHOTO
    file_id = message.photo[-1].file_id if is_photo else message.document.file_id

    user = message.from_user
    username = f"@{user.username}" if user.username else "—"
    caption = (
        f"🧾 <b>Yangi to'lov #{payment.id}</b>\n\n"
        f"👤 {user.full_name} ({username})\n"
        f"🆔 <code>{user.id}</code>\n"
        f"📦 {payment.tokens} token\n"
        f"💵 {payment.amount:,} so'm".replace(",", " ")
    )

    channel_message_id = None
    try:
        if is_photo:
            sent = await bot.send_photo(
                config.PAYMENT_CHANNEL_ID, file_id, caption=caption,
                reply_markup=review_keyboard(payment.id),
            )
        else:
            sent = await bot.send_document(
                config.PAYMENT_CHANNEL_ID, file_id, caption=caption,
                reply_markup=review_keyboard(payment.id),
            )
        channel_message_id = sent.message_id
    except Exception as exc:  # noqa: BLE001
        logger.error("Kanalga yuborishda xato: %s", exc)
        for admin in config.ADMINS:
            try:
                if is_photo:
                    await bot.send_photo(admin, file_id, caption=caption,
                                         reply_markup=review_keyboard(payment.id))
                else:
                    await bot.send_document(admin, file_id, caption=caption,
                                            reply_markup=review_keyboard(payment.id))
            except Exception as e:  # noqa: BLE001
                logger.error("Adminga yuborishda xato (%s): %s", admin, e)

    await payments.attach_receipt(payment.id, file_id, channel_message_id)
    await state.finish()
    await message.answer(
        "✅ Chekingiz qabul qilindi! Admin tasdiqlagach, tokenlar hisobingizga "
        "qo'shiladi. ⏳"
    )
