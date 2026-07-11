from aiogram.dispatcher.filters.state import State, StatesGroup


class AdminState(StatesGroup):
    waiting_new_admin = State()  # yangi admin id/forward
    waiting_channel = State()    # majburiy obuna kanali @username
