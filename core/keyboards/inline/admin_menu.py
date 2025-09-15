from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Общее меню аналитики
analytics_menu_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📊 Аналитика заказов", callback_data="analytics_orders"),
        InlineKeyboardButton(text="📈 Топ напитков", callback_data="analytics_top_drinks")
    ],
    [
        InlineKeyboardButton(text="🎁 Бесплатные заказы", callback_data="analytics_free_coffees"),
    ],
    [
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")
    ]
])
