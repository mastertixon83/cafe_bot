from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from pathlib import Path
import asyncio
from loguru import logger

# Импорты
from core.keyboards.inline.admin_menu import (
    admin_main_menu_ikb, analytics_menu_ikb, broadcast_menu_ikb, broadcast_confirm_ikb
)
from core.utils.database import postgres_client
from config import config
# Импортируем новое состояние
from core.utils.states import Broadcast

router = Router()


# --- ОСНОВНАЯ АДМИН-ПАНЕЛЬ ---

# Хэндлер для команды /admin
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != config.ADMIN_CHAT_ID:
        return
    path = Path(__file__).resolve().parent.parent.parent / "analitic_admin.png"
    photo = FSInputFile(path)
    await message.answer_photo(
        photo=photo,
        caption="Добро пожаловать в админ-панель!",
        reply_markup=admin_main_menu_ikb
    )


# Кнопка "Назад в админку"
@router.callback_query(F.data == "admin_panel_back")
async def back_to_admin_panel(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_CHAT_ID: return
    path = Path(__file__).resolve().parent.parent.parent / "analitic_admin.png"
    photo = FSInputFile(path)
    # Используем edit_media, чтобы картинка не моргала
    try:
        await callback.message.edit_media(
            media=photo,
            reply_markup=admin_main_menu_ikb
        )
        await callback.message.edit_caption(
            caption="Добро пожаловать в админ-панель!",
            reply_markup=admin_main_menu_ikb
        )
    except Exception:
        # Если старое сообщение не фото, просто отправляем новое
        await callback.message.answer_photo(
            photo=photo,
            caption="Добро пожаловать в админ-панель!",
            reply_markup=admin_main_menu_ikb
        )
        await callback.message.delete()
    await callback.answer()


# --- БЛОК АНАЛИТИКИ ---

@router.callback_query(F.data == "admin_analytics")
async def show_analytics_menu(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_CHAT_ID: return
    await callback.message.edit_caption(
        caption="Выберите раздел аналитики:",
        reply_markup=analytics_menu_ikb
    )


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


# --- БЛОК РАССЫЛКИ ---

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_menu(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_CHAT_ID: return

    record = await postgres_client.fetchrow("SELECT message_text FROM broadcast WHERE id = 1")
    current_text = record['message_text'] if record and record['message_text'] else "Текст для рассылки еще не задан."

    await callback.message.edit_caption(
        caption=f"Меню управления рассылкой.\n\n**Текущий текст:**\n\n`{current_text}`",
        reply_markup=broadcast_menu_ikb
    )


@router.callback_query(F.data == "broadcast_change_text")
async def broadcast_change_text(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_CHAT_ID: return
    await state.set_state(Broadcast.waiting_for_message)
    await callback.message.edit_caption(
        caption="Пришлите новый текст для рассылки. Вы можете использовать форматирование (жирный, курсив).\n\nЧтобы отменить, введите /cancel",
        reply_markup=None
    )


@router.message(Broadcast.waiting_for_message)
async def broadcast_text_received(message: Message, state: FSMContext):
    if message.from_user.id != config.ADMIN_CHAT_ID: return

    if message.text == "/cancel":
        await state.clear()
        # Возвращаем в админ-панель
        await admin_panel(message)
        return

    await postgres_client.execute(
        "INSERT INTO broadcast (id, message_text) VALUES (1, $1) ON CONFLICT (id) DO UPDATE SET message_text = $1",
        message.html_text  # Используем html_text чтобы сохранить форматирование
    )
    await state.clear()

    record = await postgres_client.fetchrow("SELECT message_text FROM broadcast WHERE id = 1")
    current_text = record['message_text']

    await message.answer(
        f"✅ Текст рассылки успешно обновлен!\n\n**Текущий текст:**\n\n{current_text}",
        reply_markup=broadcast_menu_ikb
    )


@router.callback_query(F.data == "broadcast_start")
async def broadcast_start(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_CHAT_ID: return

    record = await postgres_client.fetchrow("SELECT message_text FROM broadcast WHERE id = 1")
    if not record or not record['message_text']:
        await callback.answer("❌ Сначала нужно задать текст для рассылки!", show_alert=True)
        return

    users = await postgres_client.fetch("SELECT telegram_id FROM users WHERE is_active = TRUE")

    await callback.message.edit_caption(
        caption=f"Вы уверены, что хотите начать рассылку?\n\nСообщение будет отправлено `{len(users)}` пользователям.",
        reply_markup=broadcast_confirm_ikb
    )


@router.callback_query(F.data == "broadcast_confirm_no")
async def broadcast_confirm_no(callback: CallbackQuery):
    await broadcast_menu(callback)


@router.callback_query(F.data == "broadcast_confirm_yes")
async def broadcast_confirm_yes(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != config.ADMIN_CHAT_ID: return

    await callback.message.edit_caption(caption="🚀 Рассылка запущена...", reply_markup=None)

    record = await postgres_client.fetchrow("SELECT message_text FROM broadcast WHERE id = 1")
    text_to_send = record['message_text']

    users = await postgres_client.fetch("SELECT telegram_id FROM users WHERE is_active = TRUE")

    success_count = 0
    fail_count = 0

    status_message = await callback.message.answer(
        f"Начинаю рассылку для {len(users)} пользователей..."
    )

    for i, user in enumerate(users):
        user_id = user['telegram_id']
        try:
            await bot.send_message(user_id, text_to_send)
            success_count += 1
        except Exception as e:
            fail_count += 1
            logger.warning(f"Failed to send message to user {user_id}: {e}")

        # Обновляем сообщение о статусе каждые 20 пользователей или в конце
        if (i + 1) % 20 == 0 or (i + 1) == len(users):
            await status_message.edit_text(
                f"Обработано: {i + 1}/{len(users)}\n"
                f"✅ Успешно: {success_count}\n"
                f"❌ Ошибок: {fail_count}"
            )

        # Пауза 0.1 секунды между сообщениями
        await asyncio.sleep(0.1)

    await status_message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"Успешно отправлено: `{success_count}`\n"
        f"Не удалось отправить: `{fail_count}`"
    )

    # Возвращаемся в админ-панель
    await back_to_admin_panel(callback)
