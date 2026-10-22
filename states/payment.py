from aiogram.dispatcher.filters.state import State, StatesGroup


class BuyPremiumState(StatesGroup):
    waiting_receipt = State()  # data: payment_id


class ProcessFileState(StatesGroup):
    confirm = State()  # data: file_path, file_name, access
