from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from pathlib import Path
import datetime
from loguru import logger

# --- Импортируем все необходимые состояния и клавиатуры ---
from core.utils.states import Order
from core.keyboards.inline.inline_menu import (
    mainMenu_ikb, type_cofe_ikb, cup_cofe_ikb, time_cofe_ikb, ready_cofe_ikb,
    get_loyalty_ikb, partners_ikb, syrup_choice_ikb, addon_offer_ikb,
    croissant_choice_ikb
)
from core.utils.database import postgres_client
from config import config

# <<< --- ИЗМЕНЕНИЕ: ИМПОРТ МЕНЕДЖЕРА WEBSOCKET --- >>>
from core.webapp.ws.orders_ws import manager as ws_manager

router = Router()

# --- 1. ПРАЙС-ЛИСТ ---
PRICES = {
    "coffee": {
        "Эспрессо": {"250": 800, "330": 800, "430": 800},
        "Американо": {"250": 900, "330": 1100, "430": 1300},
        "Капучино": {"250": 1200, "330": 1400, "430": 1600},
        "Лате": {"250": 1200, "330": 1400, "430": 1600},
    },
    "syrup": 300,
    "croissant": 700
}


# --- 2. ФУНКЦИЯ ПОДСЧЕТА СТОИМОСТИ ---
def calculate_order_total(order_data: dict) -> int:
    """Рассчитывает общую стоимость заказа на основе данных из FSM."""
    total_price = 0
    coffee_type, cup_size = order_data.get('type'), order_data.get('cup')
    syrup, croissant = order_data.get('syrup'), order_data.get('croissant')
    if coffee_type and cup_size:
        total_price += PRICES.get("coffee", {}).get(coffee_type, {}).get(cup_size, 0)
    if syrup and syrup != "Без сиропа":
        total_price += PRICES.get("syrup", 0)
    if croissant and croissant != "Без добавок":
        total_price += PRICES.get("croissant", 0)
    return total_price


# --- Вспомогательные функции для чистоты кода ---
async def build_order_summary(state: FSMContext) -> str:
    """Собирает и форматирует итоговую информацию о заказе из данных состояния FSM."""
    data = await state.get_data()
    summary_parts = [f"☕️ Кофе: {data.get('type')}"]
    syrup, croissant = data.get('syrup'), data.get('croissant')
    if syrup and syrup != "Без сиропа":
        summary_parts.append(f"🍯 Сироп: {syrup}")
    summary_parts.append(f"📏 Объем: {data.get('cup')} мл")
    if croissant and croissant != "Без добавок":
        summary_parts.append(f"🥐 Добавка: {croissant}")
    summary_parts.append(f"⏱️ Подойдет через: {data.get('time')} минут")
    return "\n".join(summary_parts)


async def proceed_to_confirmation(callback: CallbackQuery, state: FSMContext):
    """Отображает экран подтверждения заказа с итоговой информацией, СУММОЙ и кнопками действий."""
    await state.set_state(Order.confirm)
    data = await state.get_data()
    summary_text = await build_order_summary(state)
    total_price = calculate_order_total(data)
    caption_with_price = (
        f"Проверь всё перед отправкой 👇\n\n{summary_text}\n\n💰 Сумма к оплате: {total_price} Т\n\nВсё верно?")
    user_id = callback.from_user.id
    referral_user = await postgres_client.fetchrow("SELECT free_coffees FROM referral_program WHERE user_id=$1",
                                                   user_id)
    free_coffees = referral_user['free_coffees'] if referral_user else 0
    await callback.message.edit_caption(caption=caption_with_price, reply_markup=get_loyalty_ikb(free_coffees))


async def start_msg(message: Message | CallbackQuery):
    """Отправляет приветственное сообщение с изображением и основной клавиатурой."""
    text = (f"""Привет 👋! Ты в боте кофейни Кофе на ходу.
    Мы варим кофе с собой и выносим его тебе прямо в руки — без очередей, шума и беготни.
    Просто выбери напиток, укажи через сколько подойдешь — и всё будет готово к твоему приходу.
    👇Начнем?""")
    path = Path(__file__).resolve().parent.parent.parent / "coffee-cup-fixed.jpg"
    photo = FSInputFile(path)
    if isinstance(message, Message):
        await message.answer_photo(photo=photo, caption=text, reply_markup=mainMenu_ikb)
    elif isinstance(message, CallbackQuery):
        await message.message.edit_media(media=InputMediaPhoto(media=photo, caption=text), reply_markup=mainMenu_ikb)


# --- /start ---
@router.message(CommandStart(deep_link=True))
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обрабатывает команду /start, включая обработку реферальных ссылок."""
    await state.clear()
    user_id = message.from_user.id
    user = await postgres_client.fetchrow("SELECT * FROM users WHERE telegram_id=$1", user_id)
    if not user:
        await postgres_client.insert("users", {"telegram_id": user_id, "username": message.from_user.username,
                                               "first_name": message.from_user.first_name})
    if message.text and message.text.startswith("/start ref_"):
        try:
            referrer_id = int(message.text.split('_')[1])
            if referrer_id != user_id:
                referral = await postgres_client.fetchrow("SELECT * FROM referral_links WHERE referred_id=$1", user_id)
                if not referral:
                    await postgres_client.insert("referral_links", {"referrer_id": referrer_id, "referred_id": user_id})
        except (ValueError, IndexError):
            pass
    await start_msg(message=message)


# --- Основные хендлеры меню ---
@router.callback_query(F.data == "make_order")
async def handle_text_message(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Order.type)
    await callback.message.edit_caption(caption="Какой кофе хочешь сегодня? (Выбери из списка 👇)",
                                        reply_markup=type_cofe_ikb)


@router.callback_query(F.data == "partners")
async def show_partners_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    referral_user = await postgres_client.fetchrow("SELECT free_coffees FROM referral_program WHERE user_id=$1",
                                                   user_id)
    free_coffees = referral_user['free_coffees'] if referral_user else 0
    if not referral_user:
        await postgres_client.insert("referral_program", {"user_id": user_id})
    bot_info = await callback.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    text = (
        f"**Твой бесплатный кофе ждёт!** ✨\n\nЗа каждого друга, который придёт по твоей ссылке и сделает заказ, ты получишь бесплатный кофе.\n Сейчас у тебя **{free_coffees}** бонусов.\n\nПоделись своей ссылкой:\n{referral_link}")
    await callback.message.edit_caption(caption=text, reply_markup=partners_ikb)


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await start_msg(message=callback)


# --- Шаги заказа (1-5) ---
@router.callback_query(Order.type)
async def order_type(callback: CallbackQuery, state: FSMContext):
    choice = callback.data
    if choice == "type_cancel":
        await state.clear()
        await callback.message.delete()
        await start_msg(message=callback.message)
        return
    await state.update_data(type=choice)
    if choice in ["Американо", "Капучино", "Лате"]:
        await state.set_state(Order.syrup)
        await callback.message.edit_caption(caption="Добавить сироп?", reply_markup=syrup_choice_ikb)
    else:
        await state.update_data(syrup="Без сиропа")
        await state.set_state(Order.cup)
        await callback.message.edit_caption(caption="Какой объем подойдет?", reply_markup=cup_cofe_ikb)


@router.callback_query(Order.syrup)
async def order_syrup(callback: CallbackQuery, state: FSMContext):
    choice = callback.data
    if choice == "syrup_back":
        await state.set_state(Order.type)
        await callback.message.edit_caption(caption="Какой кофе хочешь сегодня? (Выбери из списка 👇)",
                                            reply_markup=type_cofe_ikb)
        return
    syrup_map = {"syrup_caramel": "Карамельный", "syrup_vanilla": "Ванильный", "syrup_hazelnut": "Ореховый",
                 "syrup_skip": "Без сиропа"}
    await state.update_data(syrup=syrup_map.get(choice, "Без сиропа"))
    await state.set_state(Order.cup)
    await callback.message.edit_caption(caption="Какой объем подойдет?", reply_markup=cup_cofe_ikb)


@router.callback_query(Order.cup)
async def order_cup(callback: CallbackQuery, state: FSMContext):
    choice = callback.data
    if choice == "cup_back":
        data = await state.get_data()
        if data.get('type') in ["Американо", "Капучино", "Лате"]:
            await state.set_state(Order.syrup)
            await callback.message.edit_caption(caption="Добавить сироп?", reply_markup=syrup_choice_ikb)
        else:
            await state.set_state(Order.type)
            await callback.message.edit_caption(caption="Какой кофе хочешь сегодня? (Выбери из списка 👇)",
                                                reply_markup=type_cofe_ikb)
        return
    await state.update_data(cup=choice)
    await state.set_state(Order.time)
    await callback.message.edit_caption(caption="Через сколько минут подойдешь за кофе?", reply_markup=time_cofe_ikb)


@router.callback_query(Order.time)
async def order_time(callback: CallbackQuery, state: FSMContext):
    choice = callback.data
    if choice == "time_back":
        await state.set_state(Order.cup)
        await callback.message.edit_caption(caption="Выбери объем заново 👇", reply_markup=cup_cofe_ikb)
        return
    await state.update_data(time=choice)
    await state.set_state(Order.croissant)
    await callback.message.edit_caption(caption="Отлично! Хочешь добавить к кофе свежий круассан?",
                                        reply_markup=addon_offer_ikb)


@router.callback_query(Order.croissant)
async def order_addon(callback: CallbackQuery, state: FSMContext):
    choice = callback.data
    if choice == "add_croissant":
        await callback.message.edit_caption(caption="Выбери свой круассан:", reply_markup=croissant_choice_ikb)
        return
    if choice == "addon_back":
        await callback.message.edit_caption(caption="Отлично! Хочешь добавить к кофе свежий круассан?",
                                            reply_markup=addon_offer_ikb)
        return
    if choice.startswith("croissant_"):
        croissant_map = {"croissant_classic": "Классический", "croissant_chocolate": "Шоколадный",
                         "croissant_almond": "Миндальный"}
        await state.update_data(croissant=croissant_map.get(choice))
        await proceed_to_confirmation(callback, state)
        return
    if choice == "checkout":
        await state.update_data(croissant="Без добавок")
        await proceed_to_confirmation(callback, state)
        return


# --- Шаг 6: Подтверждение заказа (ПОЛНАЯ ФУНКЦИЯ С ИЗМЕНЕНИЯМИ) ---
@router.callback_query(Order.confirm)
async def order_uproove(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает финальное подтверждение заказа, изменение или использование бонусов."""
    # Убираем "часики" с кнопки
    await callback.answer()

    choice = callback.data
    user_id = callback.from_user.id

    # Обработка нажатия "Изменить заказ"
    if choice == "loyal_program":
        await state.set_state(Order.type)
        await callback.message.edit_caption(
            caption="Окей, выбери кофе заново 👇",
            reply_markup=type_cofe_ikb
        )
        return

    # Обработка нажатия "Использовать бесплатный кофе"
    if choice == "use_free_coffee":
        referral_user = await postgres_client.fetchrow(
            "SELECT free_coffees FROM referral_program WHERE user_id=$1",
            user_id
        )
        if referral_user and referral_user['free_coffees'] > 0:
            await state.update_data(use_free=True)
            summary_text = await build_order_summary(state)
            await callback.message.edit_caption(
                caption=f"✅ Кофе будет бесплатным!\n\n{summary_text}\n\nОсталось подтвердить заказ.",
                reply_markup=get_loyalty_ikb(referral_user['free_coffees'] - 1)
            )
        else:
            await callback.answer("У вас нет бесплатных кофе для списания.", show_alert=True)
        return

    # Обработка финального подтверждения "Подтвердить заказ"
    if choice == "create_order":
        await state.set_state(Order.ready)
        data = await state.get_data()
        order_is_free = data.get('use_free', False)
        total_price = calculate_order_total(data)

        # 1. Сохраняем заказ в БД и ПОЛУЧАЕМ ЕГО НАЗАД С ID
        order_db_data = {
            'type': data.get('type'),
            'cup': data.get('cup'),
            'syrup': data.get('syrup', 'Без сиропа'),
            'croissant': data.get('croissant', 'Без добавок'),
            'time': data.get('time'),
            'is_free': order_is_free,
            'user_id': user_id,
            'username': callback.from_user.username,
            'first_name': callback.from_user.first_name,
            'timestamp': datetime.datetime.now()
        }
        # Убедитесь, что ваш метод add_order возвращает созданную запись (через RETURNING *)
        new_order_record = await postgres_client.add_order(order_db_data)

        if not new_order_record:
            await callback.answer("Произошла ошибка при создании заказа. Пожалуйста, попробуйте еще раз.",
                                  show_alert=True)
            return

        # 2. Извлекаем номер заказа из полученной записи
        order_id = new_order_record['order_id']
        await state.update_data(last_order_id=order_id)

        # 3. Формируем сообщение для клиента с номером заказа
        if order_is_free:
            caption_text = (
                f"✅ Ваш заказ №{order_id} на сумму {total_price} Т оформлен (оплачено бонусом)!\n"
                f"Когда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇"
            )
            # Списываем бонусный кофе
            await postgres_client.execute(
                "UPDATE referral_program SET free_coffees = free_coffees - 1 WHERE user_id = $1",
                user_id
            )
        else:
            caption_text = (
                f"✅ Ваш заказ №{order_id} на сумму {total_price} Т оформлен!\n"
                f"Когда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇"
            )

        # 4. Отправляем сообщение пользователю
        await callback.message.edit_caption(caption=caption_text, reply_markup=ready_cofe_ikb)

        # 5. Формируем полезную нагрузку для дашборда
        order_payload = {
            "order_id": order_id,
            "type": new_order_record['type'],
            "cup": new_order_record['cup'],
            "time": new_order_record['time'],
            "status": new_order_record.get('status', 'new'),
            "syrup": new_order_record.get('syrup'),
            "croissant": new_order_record.get('croissant'),
            "is_free": new_order_record.get('is_free', False)
        }

        # 6. Отправляем данные на все открытые доски заказов через WebSocket
        await ws_manager.broadcast({
            "type": "new_order",
            "payload": order_payload
        })

        # 7. Логика начисления бонуса рефереру (без изменений)
        referral = await postgres_client.fetchrow(
            "SELECT referrer_id, rewarded FROM referral_links WHERE referred_id=$1", user_id
        )
        if referral and not referral['rewarded']:
            referrer_id = referral['referrer_id']
            await postgres_client.execute(
                "UPDATE referral_program SET free_coffees = free_coffees + 1, referred_count = referred_count + 1 WHERE user_id=$1",
                referrer_id
            )
            await postgres_client.execute(
                "UPDATE referral_links SET rewarded = TRUE WHERE referred_id = $1", user_id
            )
            await callback.bot.send_message(
                chat_id=referrer_id,
                text="🎉 Вам начислен бонус! За то, что ваш друг сделал первый заказ, вы получили один бесплатный кофе. Он уже ждет вас в разделе Приведи друга."
            )


# --- Шаг 7: Клиент подошел (ОБНОВЛЕННАЯ ВЕРСИЯ) ---
@router.callback_query(Order.ready)
async def order_ready(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Я подошел(ла)".
    Меняет статус заказа на 'arrived', уведомляет дашборд и админа.
    """
    await callback.answer("Отлично, уже несем ваш заказ!")

    data = await state.get_data()
    # Извлекаем ID заказа, который мы сохранили в FSM при его создании
    order_id = data.get('last_order_id')

    # Проверка, есть ли у нас ID заказа. Если нет, вежливо сообщаем об ошибке.
    if not order_id:
        await callback.message.edit_caption(
            caption="😕 Не удалось найти номер вашего последнего заказа. Пожалуйста, обратитесь к бариста.",
            reply_markup=None
        )
        await state.clear()
        return

    # --- НОВАЯ ЛОГИКА ---
    # 1. Обновляем статус заказа в базе данных на 'arrived'
    await postgres_client.update(
        table="orders",
        data={"status": "arrived"},
        where="order_id = $1",
        params=[order_id]
    )
    logger.info(f"Order #{order_id} status changed to 'arrived'.")

    # 2. Отправляем обновление на дашборд бариста через WebSocket
    await ws_manager.broadcast({
        "type": "status_update",
        "payload": {"order_id": order_id, "new_status": "arrived"}
    })
    # -------------------

    # Формируем и отправляем сообщение админу/бариста (ваша старая логика)
    admin_summary = await build_order_summary(state)
    total_price = calculate_order_total(data)
    is_free = data.get('use_free', False)
    text_for_admin = f"🚶‍♂️ Клиент подошел - @{callback.from_user.username} (Заказ №{order_id})\n\n{admin_summary}"
    if is_free:
        text_for_admin += "\n\n(Заказ был бесплатным)"
    else:
        text_for_admin += f"\n\n💰 Сумма к оплате: {total_price} Т"

    # Меняем сообщение у клиента, чтобы он не мог нажать кнопку еще раз
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ Бариста уведомлен. Ожидайте!",
        reply_markup=None  # Убираем клавиатуру
    )

    # Очищаем состояние, так как этот этап для клиента завершен
    await state.clear()


# --- Кнопка "Хочу Бота" ---
@router.callback_query(F.data == "buy_bot")
async def buy_bot_handler(callback: CallbackQuery):
    """Обрабатывает запрос на покупку бота."""
    await callback.answer(text="Ваша заявка принята, в ближайшее время наш менеджер с Вами свяжется.", show_alert=True)
    text = f"❗️❗️❗️ Клиент @{callback.from_user.username} хочет купить бота. Свяжись с ним НЕМЕДЛЕННО!!!"
    await callback.bot.send_message(chat_id=config.ADMIN_CHAT_ID, text=text)
