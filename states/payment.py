from aiogram.dispatcher.filters.state import State, StatesGroup


class BuyTokenState(StatesGroup):
    waiting_receipt = State()  # data: payment_id, amount


class ProcessFileState(StatesGroup):
    confirm = State()  # data: file_id, file_name, ext, token_cost, unit_count, unit_name
