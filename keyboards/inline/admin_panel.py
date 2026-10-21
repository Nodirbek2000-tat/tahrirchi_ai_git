from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.inline.callbacks import admin_cb, channel_del_cb, free_gift_cb


def free_gift_keyboard(diff: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(
            f"✅ Eski userlarga +{diff} token sovg'a qilish",
            callback_data=free_gift_cb.new(action="all"),
        ),
        InlineKeyboardButton("🆕 Faqat yangi userlarga", callback_data=free_gift_cb.new(action="new")),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=free_gift_cb.new(action="cancel")),
    )
    return kb


def admin_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📊 Statistika", callback_data=admin_cb.new(action="stats")),
        InlineKeyboardButton("📣 Reklama yuborish", callback_data=admin_cb.new(action="broadcast")),
        InlineKeyboardButton("🎁 Free token sozlash", callback_data=admin_cb.new(action="set_free")),
        InlineKeyboardButton("💵 Token narxi", callback_data=admin_cb.new(action="set_price")),
        InlineKeyboardButton("➕ Admin qo'shish", callback_data=admin_cb.new(action="add_admin")),
        InlineKeyboardButton("📢 Majburiy obuna kanallari", callback_data=admin_cb.new(action="channels")),
        InlineKeyboardButton("❌ Yopish", callback_data=admin_cb.new(action="close")),
    )
    return kb


def back_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data=admin_cb.new(action="menu")))
    return kb


def channels_menu(channels) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        title = ch.title or (f"@{ch.username}" if ch.username else str(ch.chat_id))
        kb.add(
            InlineKeyboardButton(
                f"❌ {title}", callback_data=channel_del_cb.new(id=ch.id)
            )
        )
    kb.add(InlineKeyboardButton("➕ Kanal qo'shish", callback_data=admin_cb.new(action="add_channel")))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data=admin_cb.new(action="menu")))
    return kb
