from aiogram.dispatcher.filters.state import State, StatesGroup


class AdminState(StatesGroup):
    waiting_new_admin = State()      # yangi admin id/forward
    waiting_channel = State()        # majburiy obuna kanali @username
    waiting_free_files = State()     # yangi userga beriladigan bepul fayllar soni
    confirm_free_gift = State()      # oshirilganda eski userlarga sovg'ani tasdiqlash
    waiting_premium_price = State()  # premium narxi (so'm)
    waiting_premium_user = State()   # qo'lda premium berish: "ID [kun]"
    waiting_user_files = State()     # bitta userga bepul fayl: "ID/@username soni"
