from aiogram.fsm.state import StatesGroup, State


class Order(StatesGroup):
    type = State()
    cup = State()
    time = State()
    syrup = State()
    croissant = State()
    confirm = State()
    ready = State()


class Broadcast(StatesGroup):
    waiting_for_message = State()


class AdminReport(StatesGroup):
    waiting_for_date = State()
