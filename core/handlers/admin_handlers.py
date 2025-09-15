from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from pathlib import Path

from core.keyboards.inline.admin_menu import analytics_menu_ikb
from core.utils.database import postgres_client
from config import config

router = Router()


# Хэндлер для команды /admin
@router.message(Command("admin"))
async def admin_panel(message: Message):
    # Проверяем, является ли пользователь админом
    if message.from_user.id != config.ADMIN_CHAT_ID:
        return await message.answer("❌ У вас нет доступа к этой панели.")

    path = Path(__file__).resolve().parent.parent.parent / "analitic_admin.png"
    photo = FSInputFile(path)

    await message.answer_photo(
        photo=photo,
        caption="Добро пожаловать в админ-панель!",
        reply_markup=analytics_menu_ikb
    )


# Хэндлер для кнопки "Аналитика заказов"
@router.callback_query(F.data == "analytics_orders")
async def show_orders_analytics(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_CHAT_ID:
        return await callback.answer("❌ У вас нет доступа.", show_alert=True)

    total_orders = await postgres_client.get_total_orders_count()
    daily_orders = await postgres_client.get_daily_orders_count()

    text = "**📊 Общая аналитика по заказам:**\n"
    text += f"▪️ Всего заказов: `{total_orders}`\n\n"

    text += "**📈 Заказы по дням:**\n"
    if daily_orders:
        for day in daily_orders:
            text += f"▪️ `{day['date']}`: `{day['count']}` заказов\n"
    else:
        text += "Нет данных по заказам за последние дни."

    await callback.message.edit_caption(caption=text, reply_markup=analytics_menu_ikb)


# Хэндлер для кнопки "Топ напитков"
@router.callback_query(F.data == "analytics_top_drinks")
async def show_top_drinks(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_CHAT_ID:
        return await callback.answer("❌ У вас нет доступа.", show_alert=True)

    top_drinks = await postgres_client.get_popular_drinks()

    text = "**📈 Топ-5 самых популярных напитков:**\n"
    if top_drinks:
        for i, drink in enumerate(top_drinks, 1):
            text += f"{i}. `{drink['type']}`: `{drink['count']}` заказов\n"
    else:
        text += "Нет данных по заказам."

    await callback.message.edit_caption(caption=text, reply_markup=analytics_menu_ikb)


# Хэндлер для кнопки "Бесплатные заказы"
@router.callback_query(F.data == "analytics_free_coffees")
async def show_free_coffees_analytics(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_CHAT_ID:
        return await callback.answer("❌ У вас нет доступа.", show_alert=True)

    free_orders = await postgres_client.get_free_orders_count()
    total_orders = await postgres_client.get_total_orders_count()

    text = "**🎁 Статистика по бесплатным заказам:**\n"
    text += f"▪️ Всего бесплатных заказов: `{free_orders}`\n"

    if total_orders > 0:
        free_percentage = (free_orders / total_orders) * 100
        text += f"▪️ Процент бесплатных: `{free_percentage:.1f}%`"

    await callback.message.edit_caption(caption=text, reply_markup=analytics_menu_ikb)
