from aiogram.utils.callback_data import CallbackData

# Premium sotib olish
buy_cb = CallbackData("buy", "package")           # package -> premium_30
# "Chek yuborish" tugmasi
receipt_cb = CallbackData("receipt", "payment_id")
# Admin: tasdiqlash / rad etish
review_cb = CallbackData("review", "action", "payment_id")  # action: approve|reject
# Faylni tahrir qilishni boshlash / bekor qilish
process_cb = CallbackData("process", "action")    # action: start|cancel
# Admin panel
admin_cb = CallbackData("adm", "action")           # stats|add_admin|channels|add_channel|menu|close
channel_del_cb = CallbackData("chdel", "id")       # majburiy obuna kanalini o'chirish
# Broadcast (reklama)
broadcast_cb = CallbackData("bc", "action")         # action: send|cancel
# Bepul fayllar oshirilganda eski userlarga sovg'a
free_gift_cb = CallbackData("fgift", "action")      # action: all|new|cancel
# Kirill <-> Lotin yo'nalishi
script_cb = CallbackData("scr", "dir")              # dir: cyr2lat|cyr2new|lat2cyr|cancel
# Imlo tuzatish: boshlash / bekor qilish
spell_cb = CallbackData("spell", "action")          # action: start|cancel
# Matnni o'girish: boshqa yozuvda ko'rsatish
text_cb = CallbackData("txt", "to")                 # to: new|old|cyr
