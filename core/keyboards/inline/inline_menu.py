from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

mainMenu_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="☕ Сделать заказ", callback_data="make_order")
        ],
        [
            InlineKeyboardButton(text="🔥 Акции", url="https://teletype.in/@kafe_tester_bot/_HnAALeGpj0")
        ],
        [
            InlineKeyboardButton(text="🤝 Пригласить друга", callback_data="partners")
        ],
        [
            InlineKeyboardButton(text="ℹ️ О нас", url="https://teletype.in/@kafe_tester_bot/MF1iYzAR9LB")
        ],
        [
            InlineKeyboardButton(text="❗️❗️❗️ Хочу Бота ❗️❗️❗️", callback_data="buy_bot")
        ]
    ]
)

type_cofe_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Эспрессо", callback_data="Эспрессо")],
        [InlineKeyboardButton(text="Американо", callback_data="Американо")],
        [InlineKeyboardButton(text="Капучино", callback_data="Капучино")],
        [InlineKeyboardButton(text="Лате", callback_data="Лате")],
        [InlineKeyboardButton(text="❌Отмена", callback_data="type_cancel")]
    ]
)

cup_cofe_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="250 мл", callback_data="250")],
        [InlineKeyboardButton(text="330 мл", callback_data="330")],
        [InlineKeyboardButton(text="430 мл", callback_data="430")],
        [InlineKeyboardButton(text="🔙Назад", callback_data="cup_back")]
    ]
)

time_cofe_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="5 минут", callback_data="5")],
        [InlineKeyboardButton(text="10 минут", callback_data="10")],
        [InlineKeyboardButton(text="15 минут", callback_data="15")],
        [InlineKeyboardButton(text="20 минут", callback_data="20")],
        [InlineKeyboardButton(text="🔙Назад", callback_data="time_back")]
    ]
)

ready_cofe_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Я подошел(ла)", callback_data="ready_order")]
    ]
)


# --- Клава для подтверждения заказа с бонусами ---
def get_loyalty_ikb(free_coffees: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅Подтвердить", callback_data="create_order")],
        [InlineKeyboardButton(text="🖊Изменить", callback_data="loyal_program")]
    ]
    if free_coffees > 0:
        kb.append(
            [InlineKeyboardButton(text=f"☕ Списать бесплатный кофе ({free_coffees})", callback_data="use_free_coffee")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# Новая клавиатура для раздела "Партнерская программа"
partners_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙Назад", callback_data="main_menu")
        ]
    ]
)
