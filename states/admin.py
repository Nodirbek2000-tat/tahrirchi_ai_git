from aiogram.dispatcher.filters.state import State, StatesGroup


class AdminState(StatesGroup):
    waiting_new_admin = State()    # yangi admin id/forward
    waiting_channel = State()      # majburiy obuna kanali @username
    waiting_free_tokens = State()  # yangi userga beriladigan free token soni
    waiting_token_price = State()  # 1 token narxi (so'm)
