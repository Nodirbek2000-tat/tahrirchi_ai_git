"""Premium sotib olish: karta → chek → admin tasdiqlaydi → premium faollashadi."""

import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from db.repositories import PaymentRepository, SettingRepository
from keyboards.inline import receipt_keyboard, review_keyboard
from keyboards.inline.callbacks import buy_cb, receipt_cb
from loader import bot, dp
from services.access import fmt_som, premium_price
from states import BuyPremiumState

logger = logging.getLogger(__name__)


@dp.callback_query_handler(buy_cb.filter(), state="*")
async def choose_premium(
    call: types.CallbackQuery,
    callback_data: dict,
    payments: PaymentRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    if callback_data["package"] != config.PREMIUM_PACKAGE:
        await call.answer("Bu tugma eskirgan. «💎 Premium» ni qayta bosing.", show_alert=True)
        return
    amount = await premium_price(settings)
    payment = await payments.create(
        user_id=call.from_user.id, package=config.PREMIUM_PACKAGE,
        days=config.PREMIUM_DAYS, amount=amount,
    )
    await BuyPremiumState.waiting_receipt.set()
    await state.update_data(payment_id=payment.id)

    await call.message.edit_text(
        f"💳 <b>To'lov</b>\n\n"
        f"💎 Premium: <b>{config.PREMIUM_DAYS} kun</b> — hamma imkoniyatlar cheksiz\n"
        f"💵 Summa: <b>{fmt_som(amount)} so'm</b>\n\n"
        f"Quyidagi kartaga o'tkazing:\n\n"
        f"<code>{config.CARD_NUMBER}</code>\n"
        f"👤 {config.CARD_HOLDER}\n\n"
        f"To'lovdan so'ng <b>«✅ Chek yuborish»</b> tugmasini bosing va chek rasmini yuboring.",
        reply_markup=receipt_keyboard(payment.id),
    )
    await call.answer()


@dp.callback_query_handler(receipt_cb.filter(), state=BuyPremiumState.waiting_receipt)
async def ask_receipt(call: types.CallbackQuery):
    await call.message.answer("🧾 Iltimos, to'lov chekining <b>rasmini</b> yoki faylini yuboring.")
    await call.answer()


@dp.message_handler(
    content_types=[types.ContentType.PHOTO, types.ContentType.DOCUMENT],
    state=BuyPremiumState.waiting_receipt,
)
async def receive_receipt(message: types.Message, payments: PaymentRepository, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id")
    payment = await payments.get(payment_id) if payment_id else None
    if not payment:
        await state.finish()
        await message.answer("❗ To'lov topilmadi. Qaytadan «💎 Premium» ni bosing.")
        return

    is_photo = message.content_type == types.ContentType.PHOTO
    file_id = message.photo[-1].file_id if is_photo else message.document.file_id

    user = message.from_user
    username = f"@{user.username}" if user.username else "—"
    caption = (
        f"🧾 <b>Yangi to'lov #{payment.id}</b>\n\n"
        f"👤 {user.full_name} ({username})\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💎 Premium {payment.days} kun\n"
        f"💵 {fmt_som(payment.amount)} so'm"
    )

    async def send(chat_id):
        if is_photo:
            return await bot.send_photo(chat_id, file_id, caption=caption,
                                        reply_markup=review_keyboard(payment.id))
        return await bot.send_document(chat_id, file_id, caption=caption,
                                       reply_markup=review_keyboard(payment.id))

    channel_message_id = None
    try:
        channel_message_id = (await send(config.PAYMENT_CHANNEL_ID)).message_id
    except Exception as exc:  # noqa: BLE001
        logger.error("Kanalga yuborishda xato: %s", exc)
        for admin in config.ADMINS:
            try:
                await send(admin)
            except Exception as e:  # noqa: BLE001
                logger.error("Adminga yuborishda xato (%s): %s", admin, e)

    await payments.attach_receipt(payment.id, file_id, channel_message_id)
    await state.finish()
    await message.answer("✅ Chekingiz qabul qilindi! Admin tasdiqlagach, Premium faollashadi. ⏳")
