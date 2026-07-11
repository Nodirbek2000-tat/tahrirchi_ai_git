from aiogram.dispatcher.filters.state import State, StatesGroup


class BroadcastState(StatesGroup):
    text = State()         # reklama matni (majburiy)
    photo = State()        # rasm (ixtiyoriy)
    button_name = State()  # tugma nomi (ixtiyoriy)
    button_url = State()   # tugma linki
    confirm = State()      # tasdiqlash
