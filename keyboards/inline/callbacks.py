from aiogram.utils.callback_data import CallbackData

# Token paketini tanlash
buy_cb = CallbackData("buy", "package")           # package -> pkg_10 ...
# "Chek yuborish" tugmasi
receipt_cb = CallbackData("receipt", "payment_id")
# Admin: tasdiqlash / rad etish
review_cb = CallbackData("review", "action", "payment_id")  # action: approve|reject
# Faylni tahrir qilishni boshlash / bekor qilish
process_cb = CallbackData("process", "action")    # action: start|cancel
# Admin panel
admin_cb = CallbackData("adm", "action")           # stats|add_admin|channels|add_channel|menu|close
channel_del_cb = CallbackData("chdel", "id")       # majburiy obuna kanalini o'chirish
# Tarjima tili tanlash
translate_lang_cb = CallbackData("trlang", "lang")  # lang: ru|uz|en|cancel
# Broadcast (reklama)
broadcast_cb = CallbackData("bc", "action")         # action: send|cancel
# Free token oshirilganda eski userlarga sovg'a
free_gift_cb = CallbackData("fgift", "action")      # action: all|new|cancel
# Kirill <-> Lotin yo'nalishi
script_cb = CallbackData("scr", "dir")              # dir: cyr2lat|cyr2new|lat2cyr|cancel
