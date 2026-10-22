from aiogram.dispatcher.filters.state import State, StatesGroup


class SpellState(StatesGroup):
    waiting_file = State()   # imlo tuzatish uchun fayl kutilmoqda
    confirm = State()        # data: file_path, file_name, access, unknown_is_uz
