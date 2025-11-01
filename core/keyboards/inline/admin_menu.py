# core/keyboards/inline/admin_ikb.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- ГЛАВНОЕ МЕНЮ АДМИНКИ ---
# Убрана ненужная кнопка "Назад", чтобы не было путаницы
admin_main_menu_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📊 Аналитика", callback_data="admin_analytics")],
    [InlineKeyboardButton(text="📄 Экспорт заказов", callback_data="get_report")],
    [InlineKeyboardButton(text="📮 Рассылка", callback_data="admin_broadcast")],
])

# --- ОБЩАЯ КЛАВИАТУРА ОТМЕНЫ/НАЗАД ---
# Универсальная кнопка для возврата в главное меню админки
back_to_admin_menu_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel_back")]
])

# Универсальная кнопка для отмены ввода
cancel_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_input")]
])

# --- МЕНЮ АНАЛИТИКИ ---
# Добавлена правильная кнопка "Назад"
analytics_menu_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📊 Аналитика заказов", callback_data="analytics_orders"),
        InlineKeyboardButton(text="📈 Топ напитков", callback_data="analytics_top_drinks")
    ],
    [
        InlineKeyboardButton(text="🎁 Бесплатные заказы", callback_data="analytics_free_coffees"),
    ],
    [
        InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel_back")
    ]
])

# --- МЕНЮ РАССЫЛКИ ---
# Добавлена правильная кнопка "Назад"
broadcast_menu_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✍️ Изменить текст/фото", callback_data="broadcast_change_text")],
    [InlineKeyboardButton(text="🚀 Начать рассылку", callback_data="broadcast_start")],
    [InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel_back")]
])

# Клавиатура подтверждения рассылки
broadcast_confirm_ikb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ ДА, Я УВЕРЕН", callback_data="broadcast_confirm_yes")],
    [InlineKeyboardButton(text="❌ НЕТ, ОТМЕНА", callback_data="broadcast_confirm_no")]
])

# --- МЕНЮ ЭКСПОРТА ЗАКАЗОВ ---
# Добавлена правильная кнопка "Назад"
get_report_ikb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 За сегодня", callback_data="export_today"),
            InlineKeyboardButton(text="📅 За неделю", callback_data="export_week")
        ],
        [
            InlineKeyboardButton(text="🗓 За месяц", callback_data="export_month"),
            InlineKeyboardButton(text="🗂 За все время", callback_data="export_all")
        ],
        [
            InlineKeyboardButton(text="✍️ Выбрать дату", callback_data="export_by_date")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel_back")
        ]
    ]
)
