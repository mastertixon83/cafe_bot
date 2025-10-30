# core/keyboards/inline/admin_menu.py (ПОЛНЫЙ КОД)

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Меню админ-панели
admin_main_menu_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📊 Аналитика", callback_data="admin_analytics")],
    [InlineKeyboardButton(text="📮 Рассылка", callback_data="admin_broadcast")],
    [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
])

# Меню аналитики
analytics_menu_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📊 Аналитика заказов", callback_data="analytics_orders"),
        InlineKeyboardButton(text="📈 Топ напитков", callback_data="analytics_top_drinks")
    ],
    [
        InlineKeyboardButton(text="🎁 Бесплатные заказы", callback_data="analytics_free_coffees"),
    ],
    [
        InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_panel_back")
    ]
])

# Меню рассылки
broadcast_menu_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✍️ Изменить текст", callback_data="broadcast_change_text")],
    [InlineKeyboardButton(text="🚀 Начать рассылку", callback_data="broadcast_start")],
    [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_panel_back")]
])

# Клавиатура подтверждения рассылки
broadcast_confirm_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ ДА, Я УВЕРЕН", callback_data="broadcast_confirm_yes")],
    [InlineKeyboardButton(text="❌ НЕТ, ОТМЕНА", callback_data="broadcast_confirm_no")]
])
