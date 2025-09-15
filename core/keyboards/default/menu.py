from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

mainMenu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Сделать заказ")
        ],
        [
            KeyboardButton(text="Акции", url="https://teletype.in/@kafe_tester_bot/_HnAALeGpj0"),
        ],
        [
            KeyboardButton(text="Партнерская программа"),
        ],
        [
            KeyboardButton(text="О нас"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
    input_field_placeholder="Выберите действие из меню",
    selective=True
)


rmk = ReplyKeyboardRemove()