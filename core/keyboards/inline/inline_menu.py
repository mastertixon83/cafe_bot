from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Главное меню ---
# Эта клавиатура представляет собой основное меню бота,
# предлагая пользователю ключевые действия: сделать заказ,
# посмотреть акции, узнать о партнерской программе и т.д.
mainMenu_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="☕ Сделать заказ", callback_data="make_order")],
        [InlineKeyboardButton(text="🔥 Акции", url="https://teletype.in/@kafe_tester_bot/_HnAALeGpj0")],
        [InlineKeyboardButton(text="🤝 Приведи друга", callback_data="partners")],
        [InlineKeyboardButton(text="ℹ️ О нас", url="https://teletype.in/@kafe_tester_bot/MF1iYzAR9LB")],
        [InlineKeyboardButton(text="❗️❗️❗️ Хочу Бота ❗️❗️❗️", callback_data="buy_bot")]
    ]
)

# --- Клавиатура для выбора типа кофе ---
# Появляется после того, как пользователь решил сделать заказ.
# Предлагает выбрать один из доступных видов кофе или отменить действие.
type_cofe_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Эспрессо", callback_data="Эспрессо")],
        [InlineKeyboardButton(text="Американо", callback_data="Американо")],
        [InlineKeyboardButton(text="Капучино", callback_data="Капучино")],
        [InlineKeyboardButton(text="Лате", callback_data="Лате")],
        [InlineKeyboardButton(text="❌Отмена", callback_data="type_cancel")]
    ]
)

# --- Клавиатура для выбора сиропа ---
# Предлагает пользователю добавить сироп в кофе за дополнительную плату,
# пропустить этот шаг или вернуться к предыдущему выбору.
syrup_choice_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🍯 Карамельный (+300Т)", callback_data="syrup_caramel")],
        [InlineKeyboardButton(text="🍦 Ванильный (+300Т)", callback_data="syrup_vanilla")],
        [InlineKeyboardButton(text="🌰 Ореховый (+300Т)", callback_data="syrup_hazelnut")],
        [InlineKeyboardButton(text="❌ Нет, спасибо", callback_data="syrup_skip")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="syrup_back")]
    ]
)

# --- Клавиатура для выбора объема стакана ---
# Позволяет пользователю выбрать желаемый объем напитка.
# Также содержит кнопку для возврата на предыдущий шаг.
cup_cofe_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="250 мл", callback_data="250")],
        [InlineKeyboardButton(text="330 мл", callback_data="330")],
        [InlineKeyboardButton(text="430 мл", callback_data="430")],
        [InlineKeyboardButton(text="🔙Назад", callback_data="cup_back")]
    ]
)

# --- Клавиатура для выбора времени готовности ---
# Пользователь указывает, через какое время он планирует забрать заказ.
time_cofe_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="5 минут", callback_data="5")],
        [InlineKeyboardButton(text="10 минут", callback_data="10")],
        [InlineKeyboardButton(text="15 минут", callback_data="15")],
        [InlineKeyboardButton(text="20 минут", callback_data="20")],
        [InlineKeyboardButton(text="🔙Назад", callback_data="time_back")]
    ]
)

# --- Клавиатура для предложения дополнительных товаров (допов) ---
# После выбора основных параметров напитка, бот предлагает добавить к заказу
# что-то еще (например, круассан) или сразу перейти к оформлению.
addon_offer_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🥐 Добавить круассан", callback_data="add_croissant")],
        [InlineKeyboardButton(text="✅ Перейти к оформлению", callback_data="checkout")]
    ]
)

# --- Клавиатура для выбора типа круассана ---
# Если пользователь согласился добавить круассан, эта клавиатура
# позволяет ему выбрать конкретный вид выпечки.
croissant_choice_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🥐 Классический (+700Т)", callback_data="croissant_classic")],
        [InlineKeyboardButton(text="🍫 Шоколадный (+700Т)", callback_data="croissant_chocolate")],
        [InlineKeyboardButton(text="🥨 Миндальный (+700Т)", callback_data="croissant_almond")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="addon_back")]
    ]
)

# --- Клавиатура для оповещения о готовности забрать заказ ---
# Отправляется пользователю, когда его заказ готов.
# Пользователь нажимает кнопку, чтобы уведомить бариста о своем приходе.
ready_cofe_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚶‍♂️ Я подошел(ла)", callback_data="client_arrived")],
    [InlineKeyboardButton(text="❌ Отменить заказ (в течение 3 мин)", callback_data="cancel_order")]
])


# --- Клавиатура для подтверждения заказа с учетом бонусов ---
# Эта функция создает динамическую клавиатуру. Она позволяет пользователю
# подтвердить или изменить заказ. Если у пользователя есть бесплатные
# чашки кофе, добавляется кнопка для их использования.
def get_loyalty_ikb(free_coffees: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅Подтвердить", callback_data="create_order")],
        [InlineKeyboardButton(text="🖊Изменить", callback_data="loyal_program")]
    ]
    if free_coffees > 0:
        kb.append(
            [InlineKeyboardButton(text=f"☕ Списать бесплатный кофе ({free_coffees})", callback_data="use_free_coffee")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# --- Клавиатура для раздела "Партнерская программа" ---
# Содержит только кнопку "Назад" для возврата в главное меню из
# раздела с информацией о партнерской программе.
partners_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔙Назад", callback_data="main_menu")]
    ]
)
