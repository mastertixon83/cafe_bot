from aiogram.fsm.state import StatesGroup, State

class Order(StatesGroup):
    type = State()
    cup = State()
    time = State()
    confirm = State()
    ready = State()