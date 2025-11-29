# core/handlers/admin_handlers.py

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from pathlib import Path
import datetime

# Импорты
from core.filters.is_admin import IsAdmin
from core.utils.database import postgres_client
from core.utils.states import Broadcast, AdminReport
from core.keyboards.inline.admin_menu import (
    admin_main_menu_ikb, analytics_menu_ikb, broadcast_menu_ikb,
    broadcast_confirm_ikb, get_report_ikb, cancel_ikb
)

# ИМПОРТИРУЕМ ЗАДАЧИ CELERY
from tasks import broadcast_task, export_orders_task

router = Router()
# Применяем фильтр админа ко всем хендлерам в этом файле
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# =================================================================
#               СЕРВИСНЫЕ ФУНКЦИИ (ДЛЯ ПЕРЕИСПОЛЬЗОВАНИЯ)
# =================================================================

async def send_admin_panel(bot: Bot, chat_id: int):
    """
    Отправляет главное меню админ-панели как новое сообщение.
    """
    path = Path(__file__).resolve().parent.parent.parent / "analitic_admin.png"
    photo = FSInputFile(path)
    await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption="Добро пожаловать в админ-панель!",
        reply_markup=admin_main_menu_ikb
    )


async def send_broadcast_menu(bot: Bot, chat_id: int):
    """
    Отправляет меню управления рассылкой как новое сообщение.
    """
    record = await postgres_client.fetchrow("SELECT message_text, photo_id FROM broadcast WHERE id = 1")
    current_text = record.get('message_text') if record else None
    current_photo = record.get('photo_id') if record else None
    caption = "Меню управления рассылкой.\n\n<b>Текущее сообщение:</b>\n\n"

    if not current_text and not current_photo:
        caption += "Сообщение для рассылки еще не задано."
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=broadcast_menu_ikb)
    else:
        if current_photo:
            await bot.send_photo(
                chat_id=chat_id, photo=current_photo, caption=caption + (current_text or ""),
                reply_markup=broadcast_menu_ikb
            )
        else:
            await bot.send_message(chat_id=chat_id, text=caption + current_text, reply_markup=broadcast_menu_ikb)


# =================================================================
#                       ГЛАВНАЯ АДМИН-ПАНЕЛЬ
# =================================================================

@router.message(Command("admin"))
async def admin_panel_handler(message: Message):
    """
    Хендлер для команды /admin. Вызывает сервисную функцию.
    """
    await send_admin_panel(message.bot, message.chat.id)


@router.callback_query(F.data == "admin_panel_back")
async def back_to_admin_panel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await send_admin_panel(callback.bot, callback.message.chat.id)
    await callback.answer()


@router.callback_query(F.data == "cancel_input")
async def cancel_any_input(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await send_admin_panel(callback.bot, callback.message.chat.id)
    await callback.answer("Ввод отменен.")


# =================================================================
#                       БЛОК АНАЛИТИКИ
# =================================================================

@router.callback_query(F.data == "admin_analytics")
async def show_analytics_menu(callback: CallbackQuery):
    await callback.message.edit_caption(
        caption="Выберите раздел аналитики:",
        reply_markup=analytics_menu_ikb
    )


@router.callback_query(F.data == "analytics_orders")
async def show_orders_analytics(callback: CallbackQuery):
    daily = await postgres_client.get_daily_orders_and_revenue()
    month_stats = await postgres_client.get_month_stats()

    text = "<b>📊 Общая аналитика по заказам:</b>\n"
    text += f"▪️ Всего заказов: `{month_stats['total_orders']}`\n\n"

    text += "<b>📈 Заказы по дням:</b>\n"
    if daily:
        for d in daily:
            text += (
                f"▪️ `{d['date']}`: `{d['count']}` заказов"
                f" - выручка {d['revenue']}₸\n"
            )
    else:
        text += "Нет данных по заказам за этот месяц.\n"

    text += "\n--------------------\n"
    text += f"▪️ Всего заказов: {month_stats['total_orders']}\n"
    text += f"▪️ Выручка за месяц: {month_stats['month_revenue']}₸"

    await callback.message.edit_caption(
        caption=text,
        reply_markup=analytics_menu_ikb
    )


@router.callback_query(F.data == "analytics_top_drinks")
async def show_top_drinks(callback: CallbackQuery):
    top_drinks = await postgres_client.get_popular_drinks()
    text = "<b>📈 Топ-5 самых популярных напитков:</b>\n"
    if top_drinks:
        for i, drink in enumerate(top_drinks, 1):
            text += f"{i}. `{drink['type']}`: `{drink['count']}` заказов\n"
    else:
        text += "Нет данных по заказам."
    await callback.message.edit_caption(caption=text, reply_markup=analytics_menu_ikb)


@router.callback_query(F.data == "analytics_free_coffees")
async def show_free_coffees_analytics(callback: CallbackQuery):
    free_orders = await postgres_client.get_free_orders_count()
    total_orders = await postgres_client.get_total_orders_count()
    text = "<b>🎁 Статистика по бесплатным заказам:</b>\n"
    text += f"▪️ Всего бесплатных заказов: `{free_orders}`\n"
    if total_orders > 0:
        free_percentage = (free_orders / total_orders) * 100
        text += f"▪️ Процент бесплатных: `{free_percentage:.1f}%`"
    await callback.message.edit_caption(caption=text, reply_markup=analytics_menu_ikb)


# =================================================================
#                       БЛОК ЭКСПОРТА ЗАКАЗОВ (CELERY)
# =================================================================

@router.callback_query(F.data == "get_report")
async def get_report_menu(callback: CallbackQuery):
    await callback.message.edit_caption(caption="За какой период выгрузить отчет по заказам?",
                                        reply_markup=get_report_ikb)


@router.callback_query(F.data.startswith("export_"))
async def send_report_callback(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split('_', 1)[1]

    if action == "by_date":
        await state.set_state(AdminReport.waiting_for_date)
        await callback.message.edit_caption(
            caption="Введите дату для отчета в формате `ГГГГ-ММ-ДД` (например, `2025-10-31`).",
            reply_markup=cancel_ikb
        )
        await callback.answer()
        return

    export_orders_task.delay(admin_id=callback.from_user.id, period=action)

    await callback.message.delete()
    await callback.message.answer(
        f"⏳ Задача на формирование отчета за '{action}' передана в обработку.\nОжидайте файл.")
    await send_admin_panel(callback.bot, callback.message.chat.id)


@router.message(AdminReport.waiting_for_date, F.text)
async def process_date_report(message: Message, state: FSMContext):
    date_text = message.text.strip()
    try:
        datetime.datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        await message.answer("❗️Неверный формат. Пожалуйста, введите дату в формате `ГГГГ-ММ-ДД`.",
                             reply_markup=cancel_ikb)
        return

    await state.clear()
    export_orders_task.delay(admin_id=message.from_user.id, specific_date_str=date_text)

    await message.answer(f"⏳ Задача на формирование отчета за `{date_text}` передана в обработку.\nОжидайте файл.")
    await send_admin_panel(message.bot, message.chat.id)


# =================================================================
#                       БЛОК РАССЫЛКИ (CELERY)
# =================================================================

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_menu_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await send_broadcast_menu(callback.bot, callback.message.chat.id)


@router.callback_query(F.data == "broadcast_change_text")
async def broadcast_change_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.waiting_for_message)
    await callback.message.delete()
    await callback.message.answer(
        text="Пришлите новое сообщение для рассылки.\n\nЭто может быть:\n- Просто текст\n- Картинка с подписью",
        reply_markup=cancel_ikb
    )


@router.message(Broadcast.waiting_for_message, F.text | F.photo)
async def broadcast_message_received(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else None
    text = message.caption or message.text or ""

    await postgres_client.execute(
        "UPDATE broadcast SET message_text = $1, photo_id = $2 WHERE id = 1", text, photo_id
    )
    await state.clear()

    await message.answer("✅ Сообщение для рассылки обновлено.")
    # <-- ИЗМЕНЕНО: Убрали FakeCallback, вызываем сервисную функцию напрямую
    await send_broadcast_menu(message.bot, message.chat.id)


@router.callback_query(F.data == "broadcast_start")
async def broadcast_start(callback: CallbackQuery):
    record = await postgres_client.fetchrow("SELECT message_text, photo_id FROM broadcast WHERE id = 1")
    if not record or (not record['message_text'] and not record['photo_id']):
        await callback.answer("❌ Сначала нужно задать текст или фото для рассылки!", show_alert=True)
        return

    users_count = await postgres_client.fetchval("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
    await callback.message.delete()
    await callback.message.answer(
        text=f"Вы уверены, что хотите начать рассылку?\n\nСообщение будет отправлено `{users_count}` пользователям.",
        reply_markup=broadcast_confirm_ikb
    )


@router.callback_query(F.data == "broadcast_confirm_no")
async def broadcast_confirm_no(callback: CallbackQuery, state: FSMContext):
    # <-- ИЗМЕНЕНО: Убрали FakeCallback, вызываем сервисную функцию напрямую
    await callback.message.delete()
    await send_broadcast_menu(callback.bot, callback.message.chat.id)


@router.callback_query(F.data == "broadcast_confirm_yes")
async def broadcast_confirm_yes(callback: CallbackQuery, state: FSMContext):
    """
    Запускает процесс рассылки через Celery.
    """
    broadcast_task.delay(admin_id=callback.from_user.id)
    await callback.answer("🚀 Рассылка запущена в фоне!", show_alert=False)

    # <-- ИЗМЕНЕНО: Убрали FakeCallback, вызываем сервисную функцию напрямую
    await callback.message.delete()
    await send_admin_panel(callback.bot, callback.message.chat.id)
