import asyncio
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from db.repositories import (
    AdminRepository,
    ChannelRepository,
    SettingRepository,
    StatsRepository,
    UserRepository,
)
from keyboards.inline.admin_panel import (
    admin_menu,
    back_menu,
    channels_menu,
    free_gift_keyboard,
)
from keyboards.inline.callbacks import admin_cb, channel_del_cb, free_gift_cb
from loader import bot, dp
from services.broadcast import run_personal
from states import AdminState, BroadcastState

logger = logging.getLogger(__name__)


def _fmt_som(value: int) -> str:
    return f"{value:,}".replace(",", " ")


# ---------- /admin ----------
@dp.message_handler(commands=["admin"], state="*")
async def admin_panel(message: types.Message, admins: AdminRepository, state: FSMContext):
    if not await admins.is_admin(message.from_user.id):
        return  # oddiy foydalanuvchiga javob bermaymiz
    await state.finish()
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=admin_menu())


# ---------- Bekor qilish ----------
@dp.message_handler(
    commands=["cancel"],
    state=[
        AdminState.waiting_new_admin,
        AdminState.waiting_channel,
        AdminState.waiting_free_tokens,
        AdminState.confirm_free_gift,
        AdminState.waiting_token_price,
    ],
)
async def cancel_admin(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Bekor qilindi.", reply_markup=admin_menu())


# ---------- Menyu navigatsiyasi ----------
@dp.callback_query_handler(admin_cb.filter(), state="*")
async def admin_actions(
    call: types.CallbackQuery,
    callback_data: dict,
    admins: AdminRepository,
    channels: ChannelRepository,
    stats: StatsRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    if not await admins.is_admin(call.from_user.id):
        await call.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    action = callback_data["action"]

    if action == "menu":
        await state.finish()
        await call.message.edit_text("🛠 <b>Admin panel</b>", reply_markup=admin_menu())

    elif action == "close":
        await state.finish()
        await call.message.delete()

    elif action == "stats":
        s = await stats.collect()
        free_tokens = int(await settings.get_value(config.SETTING_FREE_TOKENS, config.FREE_TOKENS))
        token_price = int(await settings.get_value(config.SETTING_TOKEN_PRICE, config.TOKEN_PRICE))
        text = (
            "📊 <b>Statistika</b>\n\n"
            "👥 <b>Foydalanuvchilar:</b>\n"
            f"• Bugun: <b>{s.users_today}</b>\n"
            f"• Kecha: <b>{s.users_yesterday}</b>\n"
            f"• Oxirgi 7 kun: <b>{s.users_week}</b>\n"
            f"• Jami: <b>{s.users_total}</b>\n\n"
            f"💰 Daromad (tasdiqlangan): <b>{_fmt_som(s.revenue_total)} so'm</b>\n"
            f"🪙 Sotilgan token: <b>{s.tokens_sold}</b>\n\n"
            f"🎁 Free token (yangi userga): <b>{free_tokens}</b>\n"
            f"💵 1 token narxi: <b>{_fmt_som(token_price)} so'm</b>\n\n"
            f"🤖 AI xarajati: <b>${s.ai_cost_usd}</b>\n"
        )
        if config.OPENAI_BUDGET_USD > 0:
            text += f"💵 AI qoldiq: <b>${s.ai_left_usd}</b>"
        else:
            text += "💵 AI qoldiq: <i>byudjet kiritilmagan (OPENAI_BUDGET_USD)</i>"
        await call.message.edit_text(text, reply_markup=back_menu())

    elif action == "set_free":
        current = int(await settings.get_value(config.SETTING_FREE_TOKENS, config.FREE_TOKENS))
        await AdminState.waiting_free_tokens.set()
        await call.message.edit_text(
            f"🎁 <b>Free token sozlash</b>\n\n"
            f"Joriy qiymat: <b>{current}</b> token\n\n"
            f"Yangi userga beriladigan token sonini (butun son) yuboring.\n\n"
            f"ℹ️ Yangi qiymat ko'proq bo'lsa, eski userlarga farqini sovg'a qilish "
            f"taklif qilinadi. Kamaytirilsa, eski userlardan token olinmaydi.\n\n"
            f"Bekor qilish: /cancel"
        )

    elif action == "set_price":
        current = int(await settings.get_value(config.SETTING_TOKEN_PRICE, config.TOKEN_PRICE))
        await AdminState.waiting_token_price.set()
        await call.message.edit_text(
            f"💵 <b>Token narxi sozlash</b>\n\n"
            f"Joriy qiymat: <b>{_fmt_som(current)} so'm</b> / 1 token\n\n"
            f"1 token narxini (so'mda, butun son) yuboring. Masalan: 300\n\n"
            f"Bekor qilish: /cancel"
        )

    elif action == "broadcast":
        await BroadcastState.text.set()
        await call.message.edit_text(
            "📣 <b>Reklama yuborish</b>\n\n"
            "1-qadam: Reklama <b>matnini</b> yuboring.\n\n"
            "Bekor qilish: /cancel"
        )

    elif action == "add_admin":
        await AdminState.waiting_new_admin.set()
        await call.message.edit_text(
            "➕ Yangi admin <b>Telegram ID</b> raqamini yuboring "
            "yoki uning istalgan xabarini <b>forward</b> qiling.\n\n"
            "Bekor qilish: /cancel"
        )

    elif action == "channels":
        channel_list = await channels.all()
        text = "📢 <b>Majburiy obuna kanallari</b>\n\n"
        text += "Ro'yxat bo'sh." if not channel_list else "O'chirish uchun kanalni bosing:"
        await call.message.edit_text(text, reply_markup=channels_menu(channel_list))

    elif action == "add_channel":
        await AdminState.waiting_channel.set()
        await call.message.edit_text(
            "➕ Kanal <b>@username</b> ini yuboring (yoki -100... ID).\n\n"
            "⚠️ Bot o'sha kanalda <b>admin</b> bo'lishi shart!\n\n"
            "Bekor qilish: /cancel"
        )

    await call.answer()


# ---------- Kanalni o'chirish ----------
@dp.callback_query_handler(channel_del_cb.filter(), state="*")
async def delete_channel(
    call: types.CallbackQuery,
    callback_data: dict,
    admins: AdminRepository,
    channels: ChannelRepository,
):
    if not await admins.is_admin(call.from_user.id):
        await call.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return
    await channels.remove(int(callback_data["id"]))
    channel_list = await channels.all()
    text = "📢 <b>Majburiy obuna kanallari</b>\n\n"
    text += "Ro'yxat bo'sh." if not channel_list else "O'chirish uchun kanalni bosing:"
    await call.message.edit_text(text, reply_markup=channels_menu(channel_list))
    await call.answer("O'chirildi ✅")


# ---------- Yangi admin qabul qilish ----------
@dp.message_handler(state=AdminState.waiting_new_admin, content_types=types.ContentType.ANY)
async def receive_new_admin(
    message: types.Message, admins: AdminRepository, state: FSMContext
):
    new_id = None
    if message.forward_from:
        new_id = message.forward_from.id
    elif message.text and message.text.strip().lstrip("-").isdigit():
        new_id = int(message.text.strip())

    if not new_id:
        await message.answer(
            "❗ ID topilmadi. Raqam yuboring yoki xabarni forward qiling "
            "(agar forward ko'rinmasa, foydalanuvchi maxfiylikni yoqqan — ID yozing)."
        )
        return

    await admins.add(new_id, message.from_user.id)
    await state.finish()
    await message.answer(
        f"✅ <code>{new_id}</code> admin qilib qo'shildi.", reply_markup=admin_menu()
    )


# ---------- Yangi kanal qabul qilish ----------
def _parse_channel(raw: str) -> str:
    raw = raw.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    return raw


@dp.message_handler(state=AdminState.waiting_channel, content_types=types.ContentType.ANY)
async def receive_channel(
    message: types.Message, channels: ChannelRepository, state: FSMContext
):
    if not message.text:
        await message.answer("❗ Kanal @username yoki ID sini matn ko'rinishida yuboring.")
        return

    raw = _parse_channel(message.text)
    target = int(raw) if raw.lstrip("-").isdigit() else f"@{raw}"

    try:
        chat = await bot.get_chat(target)
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_chat xato: %s", exc)
        await message.answer(
            "❌ Kanal topilmadi. @username to'g'ri ekanini va bot kanalga "
            "qo'shilganini tekshiring."
        )
        return

    try:
        member = await bot.get_chat_member(chat.id, bot.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_chat_member(bot) xato: %s", exc)
        await message.answer("❌ Botning kanaldagi holatini tekshirib bo'lmadi.")
        return

    if member.status not in ("administrator", "creator"):
        await message.answer(
            f"⚠️ Bot <b>{chat.title}</b> kanalida admin emas!\n"
            "Avval botni o'sha kanalga admin qiling, keyin qayta urinib ko'ring."
        )
        return

    await channels.add(chat.id, chat.username, chat.title or "Kanal", message.from_user.id)
    await state.finish()
    await message.answer(
        f"✅ <b>{chat.title}</b> majburiy obunaga qo'shildi.",
        reply_markup=admin_menu(),
    )


# ---------- Free token sozlash ----------
@dp.message_handler(state=AdminState.waiting_free_tokens, content_types=types.ContentType.ANY)
async def receive_free_tokens(
    message: types.Message,
    users: UserRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❗ Faqat butun son yuboring. Masalan: 30")
        return
    value = int(text)
    if value > 1_000_000:
        await message.answer("❗ Juda katta son. Kichikroq qiymat yuboring.")
        return

    old = int(await settings.get_value(config.SETTING_FREE_TOKENS, config.FREE_TOKENS))

    # Kamaytirilsa yoki o'zgarmasa — faqat yangi userlarga ta'sir qiladi
    if value <= old:
        await settings.set_value(config.SETTING_FREE_TOKENS, value)
        await state.finish()
        note = (
            "Eski userlardan token olinmaydi — bu faqat yangi userlarga ta'sir qiladi."
            if value < old else "Qiymat o'zgarmadi."
        )
        await message.answer(
            f"✅ Free token: <b>{old}</b> → <b>{value}</b>\n{note}",
            reply_markup=admin_menu(),
        )
        return

    # Oshirilsa — eski userlarga farqini sovg'a qilishni taklif qilamiz
    diff = value - old
    total = await users.count()
    await state.update_data(free_old=old, free_new=value)
    await AdminState.confirm_free_gift.set()
    await message.answer(
        f"🎁 Free token: <b>{old}</b> → <b>{value}</b>\n\n"
        f"Botda <b>{_fmt_som(total)}</b> ta eski user bor.\n"
        f"Ularning har biriga <b>+{diff} token</b> sovg'a qilinsinmi?\n\n"
        f"Har biriga xabar boradi: «Sizga admin tomonidan {diff} ta token sovg'a "
        f"qilindi» va joriy balansi.",
        reply_markup=free_gift_keyboard(diff),
    )


@dp.callback_query_handler(free_gift_cb.filter(), state=AdminState.confirm_free_gift)
async def confirm_free_gift(
    call: types.CallbackQuery,
    callback_data: dict,
    admins: AdminRepository,
    users: UserRepository,
    settings: SettingRepository,
    state: FSMContext,
):
    if not await admins.is_admin(call.from_user.id):
        await call.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    data = await state.get_data()
    old, new = data.get("free_old"), data.get("free_new")
    action = callback_data["action"]
    await state.finish()
    await call.answer()

    if action == "cancel" or new is None:
        await call.message.edit_text(
            "❌ Bekor qilindi. Free token o'zgarmadi.", reply_markup=admin_menu()
        )
        return

    if action == "new":
        await settings.set_value(config.SETTING_FREE_TOKENS, new)
        await call.message.edit_text(
            f"✅ Free token: <b>{old}</b> → <b>{new}</b>\nFaqat yangi userlarga ta'sir qiladi.",
            reply_markup=admin_menu(),
        )
        return

    # action == "all": eski userlarga farqini sovg'a qilish
    diff = new - old
    updated = await users.add_tokens_all(diff)
    await settings.set_value(config.SETTING_FREE_TOKENS, new)
    balances = await users.balances()

    await call.message.edit_text(
        f"✅ Free token: <b>{old}</b> → <b>{new}</b>\n"
        f"🎁 <b>{_fmt_som(updated)}</b> ta userga <b>+{diff}</b> token qo'shildi.\n"
        f"📤 Xabarlar yuborilmoqda... Yakunda hisobot keladi."
    )

    messages = [
        (
            user_id,
            f"🎁 Sizga admin tomonidan <b>{diff} ta token</b> sovg'a qilindi!\n"
            f"💰 Balansingiz: <b>{tokens}</b> token.",
        )
        for user_id, tokens in balances
    ]
    admin_id = call.from_user.id

    async def job():
        sent, failed = await run_personal(bot, messages)
        try:
            await bot.send_message(
                admin_id,
                f"✅ Sovg'a xabarlari yakunlandi.\n📤 Yuborildi: <b>{sent}</b>\n"
                f"❌ Yuborilmadi (botni bloklaganlar): <b>{failed}</b>",
                reply_markup=admin_menu(),
            )
        except Exception:  # noqa: BLE001
            pass

    asyncio.create_task(job())


# ---------- Token narxi sozlash ----------
@dp.message_handler(state=AdminState.waiting_token_price, content_types=types.ContentType.ANY)
async def receive_token_price(
    message: types.Message, settings: SettingRepository, state: FSMContext
):
    text = (message.text or "").strip().replace(" ", "")
    if not text.isdigit():
        await message.answer("❗ Faqat butun son yuboring. Masalan: 300")
        return
    value = int(text)
    if value <= 0 or value > 10_000_000:
        await message.answer("❗ Noto'g'ri narx. 1 dan katta, haqiqiy qiymat yuboring.")
        return
    await settings.set_value(config.SETTING_TOKEN_PRICE, value)
    await state.finish()
    await message.answer(
        f"✅ 1 token narxi <b>{_fmt_som(value)} so'm</b> qilib o'rnatildi.\n"
        f"Paketlar narxi avtomatik yangilanadi (token soni × narx).",
        reply_markup=admin_menu(),
    )
