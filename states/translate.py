from aiogram.dispatcher.filters.state import State, StatesGroup


class TranslateState(StatesGroup):
    waiting_file = State()       # tarjima tugmasi bosilgan, fayl kutilmoqda
    choosing_language = State()  # til tanlash (data: file_path, file_name, token_cost, source, is_admin)
