from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_WORD = "📝 Word tahrir"
BTN_EXCEL = "📊 Excel tahrir"
BTN_PDF = "📕 PDF tahrir"
BTN_PPTX = "📽 Prezentatsiya tahrir"
BTN_TRANSLATE = "🌐 Fayllarni tarjima qilish"
BTN_BALANCE = "💰 Balansim"
BTN_BUY = "🛒 Yangi sotib olish"

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(BTN_WORD), KeyboardButton(BTN_EXCEL)],
        [KeyboardButton(BTN_PDF), KeyboardButton(BTN_PPTX)],
        [KeyboardButton(BTN_TRANSLATE)],
        [KeyboardButton(BTN_BALANCE)],
        [KeyboardButton(BTN_BUY)],
    ],
    resize_keyboard=True,
)
