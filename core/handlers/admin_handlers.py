# core/handlers/admin_handlers.py

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from pathlib import Path
import asyncio
import io
import csv
import datetime
from typing import Union
from loguru import logger

# Импорты
from core.filters.is_admin import IsAdmin
from core.utils.database import postgres_client
from config import config
from core.utils.states import Broadcast, AdminReport
from core.keyboards.inline.admin_ikb import (
    admin_main_menu_ikb, analytics_menu_ikb, broadcast_menu_ikb,
    broadcast_confirm_ikb, get_report_ikb, cancel_ikb
)

router = Router()
# Применяем фильтр админа ко всем хендлерам в этом файле
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# =================================================================
#               ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =================================================================

async def generate_csv_from_orders(orders: list) -> io.StringIO:
    """
    Генерирует CSV-файл в памяти из списка заказов.
    """
    output = io.StringIO()
    fieldnames = [
        'ID Заказа', 'Дата и время', 'Клиент', 'Username', 'Напиток', 'Сироп',
        'Объем', 'Добавка', 'Сумма', 'Статус Заказа', 'Статус Оплаты'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    for order in orders:
        writer.writerow({
            'ID Заказа': order['order_id'],
            'Дата и время': order['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
            'Клиент': order['first_name'],
            'Username': f"@{order['username']}" if order['username'] else 'N/A',
            'Напиток': order['type'],
            'Сироп': order['syrup'],
            'Объем': f"{order['cup']} мл",
            'Добавка': order['croissant'],
            'Сумма': order['total_price'],
            'Статус Заказа': order['status'],
            'Статус Оплаты': order['payment_status'],
        })
    output.seek(0)
    return output


async def send_csv_report(message_or_callback: Union[Message, CallbackQuery], orders: list, report_name: str):
    """
    Универсальная функция для отправки CSV-отчета.
    """
    if not orders:
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text("За выбранный период заказов не найдено.")
        else:
            await message_or_callback.answer("За выбранный период заказов не найдено.")
        return

    csv_file = await generate_csv_from_orders(orders)
    file_to_send = BufferedInputFile(
        file=csv_file.getvalue().encode('utf-8'),
        filename=f"report_{report_name}_{datetime.date.today()}.csv"
    )

    caption = f"📄 Ваш отчет '{report_name}'.\nВсего заказов: {len(orders)}"

    if isinstance(message_or_callback, CallbackQuery):
        # Отправляем новый документ и удаляем старое сообщение с кнопками
        await message_or_callback.message.answer_document(document=file_to_send, caption=caption)
        await message_or_callback.message.delete()
    else:
        await message_or_callback.answer_document(document=file_to_send, caption=caption)


# =================================================================
#                       ГЛАВНАЯ АДМИН-ПАНЕЛЬ
# =================================================================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    """
    Отправляет главное меню админ-панели.
    """
    path = Path(__file__).resolve().parent.parent.parent / "analitic_admin.png"
    photo = FSInputFile(path)
    await message.answer_photo(
        photo=photo,
        caption="Добро пожаловать в админ-панель!",
        reply_markup=admin_main_menu_ikb
    )


@router.callback_query(F.data == "admin_panel_back")
async def back_to_admin_panel(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает в главное меню админ-панели.
    """
    await state.clear()
    await callback.message.delete()
    await admin_panel(callback.message)
    await callback.answer()


@router.callback_query(F.data == "cancel_input")
async def cancel_any_input(callback: CallbackQuery, state: FSMContext):
    """Отменяет любой ввод (даты, текста) и возвращает в админку."""
    await state.clear()
    await callback.message.delete()
    await admin_panel(callback.message)
    await callback.answer("Ввод отменен.")


# =================================================================
#                       БЛОК АНАЛИТИКИ
# =================================================================

@router.callback_query(F.data == "admin_analytics")
async def show_analytics_menu(callback: CallbackQuery):
    """Отображает меню выбора разделов аналитики."""
    await callback.message.edit_caption(caption="Выберите раздел аналитики:", reply_markup=analytics_menu_ikb)


@router.callback_query(F.data == "analytics_orders")
async def show_orders_analytics(callback: CallbackQuery):
    """Показывает общую статистику по количеству заказов и по дням."""
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


@router.callback_query(F.data == "analytics_top_drinks")
async def show_top_drinks(callback: CallbackQuery):
    """Показывает топ-5 самых популярных напитков."""
    top_drinks = await postgres_client.get_popular_drinks()
    text = "**📈 Топ-5 самых популярных напитков:**\n"
    if top_drinks:
        for i, drink in enumerate(top_drinks, 1):
            text += f"{i}. `{drink['type']}`: `{drink['count']}` заказов\n"
    else:
        text += "Нет данных по заказам."
    await callback.message.edit_caption(caption=text, reply_markup=analytics_menu_ikb)


@router.callback_query(F.data == "analytics_free_coffees")
async def show_free_coffees_analytics(callback: CallbackQuery):
    """Показывает статистику по бесплатным заказам."""
    free_orders = await postgres_client.get_free_orders_count()
    total_orders = await postgres_client.get_total_orders_count()
    text = "**🎁 Статистика по бесплатным заказам:**\n"
    text += f"▪️ Всего бесплатных заказов: `{free_orders}`\n"
    if total_orders > 0:
        free_percentage = (free_orders / total_orders) * 100
        text += f"▪️ Процент бесплатных: `{free_percentage:.1f}%`"
    await callback.message.edit_caption(caption=text, reply_markup=analytics_menu_ikb)


# =================================================================
#                       БЛОК ЭКСПОРТА ЗАКАЗОВ
# =================================================================

@router.callback_query(F.data == "get_report")
async def get_report_menu(callback: CallbackQuery):
    """Показывает меню выбора периода для отчета."""
    await callback.message.edit_caption(caption="За какой период выгрузить отчет по заказам?",
                                        reply_markup=get_report_ikb)


@router.callback_query(F.data.startswith("export_"))
async def send_report_callback(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор периода для экспорта или запрашивает дату.
    """
    # Убираем 'export_' из callback.data
    action = callback.data[7:]

    if action == "by_date":
        await state.set_state(AdminReport.waiting_for_date)
        await callback.message.edit_caption(
            caption="Введите дату для отчета в формате `ГГГГ-ММ-ДД` (например, `2025-10-31`).",
            reply_markup=cancel_ikb
        )
        await callback.answer()
        return

    await callback.answer(f"⏳ Формирую отчет за '{action}'...", show_alert=False)

    try:
        orders = await postgres_client.get_orders_for_export(action)
        await send_csv_report(callback, orders, action)
    except Exception as e:
        logger.error(f"Ошибка при генерации отчета: {e}", exc_info=True)
        await callback.message.answer("❌ Произошла ошибка при создании отчета.")


@router.message(AdminReport.waiting_for_date, F.text)
async def process_date_report(message: Message, state: FSMContext):
    """
    Получает дату от админа, генерирует и отправляет отчет за этот день.
    """
    try:
        report_date = datetime.datetime.strptime(message.text.strip(), "%Y-%m-%d").date()
    except ValueError:
        await message.answer("❗️Неверный формат. Пожалуйста, введите дату в формате `ГГГГ-ММ-ДД`.",
                             reply_markup=cancel_ikb)
        return

    await state.clear()
    await message.answer(f"⏳ Формирую отчет за `{report_date}`...")

    try:
        orders = await postgres_client.get_orders_by_date(report_date)
        await send_csv_report(message, orders, str(report_date))
    except Exception as e:
        logger.error(f"Ошибка при генерации отчета по дате: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при создании отчета по дате.")


# =================================================================
#                       БЛОК РАССЫЛКИ
# =================================================================

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_menu(callback: CallbackQuery, state: FSMContext):
    """
    Отображает меню управления рассылкой.
    """
    await state.clear()
    record = await postgres_client.fetchrow("SELECT message_text, photo_id FROM broadcast WHERE id = 1")
    current_text = record.get('message_text') if record else None
    current_photo = record.get('photo_id') if record else None
    caption = "Меню управления рассылкой.\n\n**Текущее сообщение:**\n\n"
    await callback.message.delete()
    if not current_text and not current_photo:
        caption += "Сообщение для рассылки еще не задано."
        await callback.message.answer(text=caption, reply_markup=broadcast_menu_ikb)
    else:
        if current_photo:
            await callback.message.answer_photo(
                photo=current_photo, caption=caption + (current_text or ""), reply_markup=broadcast_menu_ikb
            )
        else:
            await callback.message.answer(text=caption + current_text, reply_markup=broadcast_menu_ikb)


@router.callback_query(F.data == "broadcast_change_text")
async def broadcast_change_text(callback: CallbackQuery, state: FSMContext):
    """Переводит админа в состояние ожидания нового сообщения для рассылки."""
    await state.set_state(Broadcast.waiting_for_message)
    await callback.message.delete()
    await callback.message.answer(
        text="Пришлите новое сообщение для рассылки.\n\nЭто может быть:\n- Просто текст\n- Картинка с подписью",
        reply_markup=cancel_ikb
    )


@router.message(Broadcast.waiting_for_message, F.text | F.photo)
async def broadcast_message_received(message: Message, state: FSMContext):
    """
    Ловит сообщение от админа (текст или фото) и сохраняет его в БД.
    """
    photo_id = message.photo[-1].file_id if message.photo else None
    text = message.caption or message.text or ""

    await postgres_client.execute(
        "UPDATE broadcast SET message_text = $1, photo_id = $2 WHERE id = 1", text, photo_id
    )
    await state.clear()

    await message.answer("✅ Сообщение для рассылки обновлено. Вот как оно выглядит:")

    # Вызываем функцию меню, чтобы показать обновленное превью
    # Для этого нам нужен объект CallbackQuery, создадим "фейковый"
    class FakeCallback:
        def __init__(self, msg):
            self.message = msg
            self.from_user = msg.from_user

        async def answer(self): pass

    await broadcast_menu(FakeCallback(message), state)


@router.callback_query(F.data == "broadcast_start")
async def broadcast_start(callback: CallbackQuery):
    """
    Запрашивает у админа финальное подтверждение перед началом рассылки.
    """
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
    """Обрабатывает отмену начала рассылки."""
    await broadcast_menu(callback, state)


@router.callback_query(F.data == "broadcast_confirm_yes")
async def broadcast_confirm_yes(callback: CallbackQuery, bot: Bot):
    """
    Запускает процесс рассылки сообщений всем активным пользователям.
    """
    await callback.message.edit_text(text="🚀 Рассылка запущена...", reply_markup=None)

    record = await postgres_client.fetchrow("SELECT message_text, photo_id FROM broadcast WHERE id = 1")
    text_to_send = record['message_text']
    photo_to_send = record['photo_id']

    users = await postgres_client.fetch("SELECT telegram_id FROM users WHERE is_active = TRUE")

    success_count = 0
    fail_count = 0
    total_users = len(users)

    status_message = await callback.message.answer(f"Начинаю рассылку для {total_users} пользователей...")

    for i, user in enumerate(users):
        user_id = user['telegram_id']
        try:
            if photo_to_send:
                await bot.send_photo(user_id, photo_to_send, caption=text_to_send)
            else:
                await bot.send_message(user_id, text_to_send)
            success_count += 1
        except Exception as e:
            fail_count += 1
            logger.warning(f"Failed to send message to user {user_id}: {e}")
            await postgres_client.update("users", {"is_active": False}, "telegram_id = $1", [user_id])

        if (i + 1) % 20 == 0 or (i + 1) == total_users:
            try:
                await status_message.edit_text(
                    f"Обработано: {i + 1}/{total_users}\n"
                    f"✅ Успешно: {success_count}\n"
                    f"❌ Ошибок (юзеры деактивированы): {fail_count}"
                )
            except Exception:
                pass
        await asyncio.sleep(0.1)

    await status_message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"Успешно отправлено: `{success_count}`\n"
        f"Не удалось отправить (и деактивировано): `{fail_count}`"
    )

    await asyncio.sleep(2)

    # Возвращаемся в админку
    class FakeCallback:
        def __init__(self, msg):
            self.message = msg
            self.from_user = msg.from_user

        async def answer(self): pass

    await back_to_admin_panel(FakeCallback(status_message), FSMContext(storage=router.storage,
                                                                       key=StorageKey(bot.id, callback.from_user.id,
                                                                                      callback.from_user.id)))
