import logging

from aiogram import types

from data import config
from db.models import PaymentStatus
from db.repositories import PaymentRepository, UserRepository
from keyboards.inline.callbacks import review_cb
from loader import bot, dp

logger = logging.getLogger(__name__)


@dp.callback_query_handler(review_cb.filter(), state="*")
async def review_payment(
    call: types.CallbackQuery,
    callback_data: dict,
    payments: PaymentRepository,
    users: UserRepository,
):
    if call.from_user.id not in config.ADMINS:
        await call.answer("⛔ Sizda ruxsat yo'q.", show_alert=True)
        return

    action = callback_data["action"]
    payment_id = int(callback_data["payment_id"])
    status = PaymentStatus.APPROVED if action == "approve" else PaymentStatus.REJECTED

    payment = await payments.resolve(payment_id, status, call.from_user.id)
    if payment is None:
        await call.answer("Bu to'lov allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    if action == "approve":
        await users.add_tokens(payment.user_id, payment.tokens)
        suffix = f"\n\n✅ <b>Tasdiqladi:</b> {call.from_user.full_name}"
        try:
            await bot.send_message(
                payment.user_id,
                f"✅ To'lovingiz tasdiqlandi!\n🪙 <b>{payment.tokens} token</b> "
                f"hisobingizga qo'shildi.",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Foydalanuvchiga xabar yuborilmadi: %s", exc)
    else:
        suffix = f"\n\n❌ <b>Rad etdi:</b> {call.from_user.full_name}"
        try:
            await bot.send_message(
                payment.user_id,
                "❌ To'lovingiz rad etildi. Agar xatolik bo'lsa, admin bilan "
                "bog'laning.",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Foydalanuvchiga xabar yuborilmadi: %s", exc)

    caption = call.message.caption or call.message.text or ""
    try:
        if call.message.caption is not None:
            await call.message.edit_caption(caption + suffix, reply_markup=None)
        else:
            await call.message.edit_text(caption + suffix, reply_markup=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Xabarni tahrirlashda xato: %s", exc)

    await call.answer("Bajarildi ✅")
