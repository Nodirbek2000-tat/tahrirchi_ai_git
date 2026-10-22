from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_WORD = "📝 Word tahrir"
BTN_EXCEL = "📊 Excel tahrir"
BTN_PDF = "📕 PDF tahrir"
BTN_PPTX = "📽 Prezentatsiya tahrir"
BTN_SPELL = "✍️ Imlo tuzatish"
BTN_SCRIPT = "🔤 Kirill ↔ Lotin"
BTN_ACCOUNT = "👤 Hisobim"
BTN_PREMIUM = "💎 Premium"

# Eski menyu tugmalari (userlarda eski klaviatura qolgan bo'lishi mumkin)
LEGACY_BUTTONS = ("🌐 Fayllarni tarjima qilish", "💰 Balansim", "🛒 Yangi sotib olish")

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(BTN_WORD), KeyboardButton(BTN_EXCEL)],
        [KeyboardButton(BTN_PDF), KeyboardButton(BTN_PPTX)],
        [KeyboardButton(BTN_SPELL), KeyboardButton(BTN_SCRIPT)],
        [KeyboardButton(BTN_ACCOUNT), KeyboardButton(BTN_PREMIUM)],
    ],
    resize_keyboard=True,
)
