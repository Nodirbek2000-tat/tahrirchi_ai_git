from aiogram.dispatcher.filters.state import State, StatesGroup


class ScriptState(StatesGroup):
    waiting_file = State()        # "Kirill ↔ Lotin" bosilgan, fayl kutilmoqda
    choosing_direction = State()  # yo'nalish tanlash (data: file_path, file_name, token_cost, ...)
