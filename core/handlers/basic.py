from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto, InlineKeyboardMarkup, \
    InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from pathlib import Path
import datetime
import uuid
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
from core.webapp.ws.orders_ws import manager as ws_manager
from core.utils.helpers import calculate_order_total
from core.services.epay_service import epay_service

router = Router()


# --- Вспомогательные функции ---
async def build_order_summary(state: FSMContext) -> str:
    """
    Собирает текстовое описание заказа из данных состояния FSM.

    Args:
        state (FSMContext): Контекст состояния FSM, содержащий данные заказа.

    Returns:
        str: Многострочная строка с описанием заказа.
    """
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
    """
    Переводит пользователя на шаг подтверждения заказа.

    Функция устанавливает состояние Order.confirm, формирует итоговое
    сообщение с составом заказа и его стоимостью, а также добавляет
    клавиатуру с возможностью использования бонусного кофе.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
        state (FSMContext): Контекст состояния FSM.
    """
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
    """
    Отправляет стартовое сообщение с изображением и главным меню.

    Может быть вызвана как для нового сообщения (Message), так и для
    редактирования существующего (CallbackQuery).

    Args:
        message (Message | CallbackQuery): Объект сообщения или callback-запроса.
    """
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
    """
    Обрабатывает команду /start.

    Очищает состояние FSM, регистрирует нового пользователя (если его нет),
    обрабатывает deep-link с реферальным кодом и отправляет стартовое сообщение.

    Args:
        message (Message): Объект сообщения от пользователя.
        state (FSMContext): Контекст состояния FSM.
    """
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
    """
    Обрабатывает нажатие на кнопку "Сделать заказ".

    Устанавливает состояние Order.type и предлагает пользователю
    выбрать тип кофе.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
        state (FSMContext): Контекст состояния FSM.
    """
    await state.set_state(Order.type)
    await callback.message.edit_caption(caption="Какой кофе хочешь сегодня? (Выбери из списка 👇)",
                                        reply_markup=type_cofe_ikb)


@router.callback_query(F.data == "partners")
async def show_partners_info(callback: CallbackQuery):
    """
    Показывает информацию о партнерской (реферальной) программе.

    Отображает количество бонусных чашек кофе у пользователя и его
    уникальную реферальную ссылку для приглашения друзей.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
    """
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
    """
    Возвращает пользователя в главное меню.

    Очищает состояние FSM и отправляет стартовое сообщение.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
        state (FSMContext): Контекст состояния FSM.
    """
    await state.clear()
    await start_msg(message=callback)


# --- Шаги заказа (1-5) ---
@router.callback_query(Order.type)
async def order_type(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор типа кофе (шаг 1).

    Сохраняет выбор в FSM. Если выбран напиток, в который можно добавить
    сироп, переходит к шагу выбора сиропа. В противном случае - к выбору объема.
    Также обрабатывает отмену заказа.

    Args:
        callback (CallbackQuery): Объект callback-запроса с выбором типа.
        state (FSMContext): Контекст состояния FSM.
    """
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
    """
    Обрабатывает выбор сиропа (шаг 2).

    Сохраняет выбор сиропа в FSM и переводит на следующий шаг - выбор объема.
    Также обрабатывает кнопку "Назад".

    Args:
        callback (CallbackQuery): Объект callback-запроса с выбором сиропа.
        state (FSMContext): Контекст состояния FSM.
    """
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
    """
    Обрабатывает выбор объема стакана (шаг 3).

    Сохраняет выбор в FSM и переводит на следующий шаг - выбор времени.
    Также обрабатывает кнопку "Назад".

    Args:
        callback (CallbackQuery): Объект callback-запроса с выбором объема.
        state (FSMContext): Контекст состояния FSM.
    """
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
    """
    Обрабатывает выбор времени готовности заказа (шаг 4).

    Сохраняет выбор в FSM и переводит на следующий шаг - предложение добавки.
    Также обрабатывает кнопку "Назад".

    Args:
        callback (CallbackQuery): Объект callback-запроса с выбором времени.
        state (FSMContext): Контекст состояния FSM.
    """
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
    """
    Обрабатывает выбор добавки (круассана) (шаг 5).

    Обрабатывает нажатие на кнопки добавления круассана, выбора конкретного
    круассана или отказа от добавки. После выбора переводит на шаг
    подтверждения заказа.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
        state (FSMContext): Контекст состояния FSM.
    """
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


# --- Шаг 6: Подтверждение заказа ---
@router.callback_query(Order.confirm)
async def order_approve(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает подтверждение заказа (шаг 6).

    Обрабатывает кнопки "Подтвердить", "Использовать бесплатный кофе" и "Назад".
    При подтверждении создает запись о заказе в базе данных, оповещает
    бариста через WebSocket, начисляет реферальный бонус (если применимо)
    и показывает пользователю финальное сообщение с кнопкой "Я подошел".

    Args:
        callback (CallbackQuery): Объект callback-запроса.
        state (FSMContext): Контекст состояния FSM.
    """
    await callback.answer()
    choice = callback.data
    user_id = callback.from_user.id
    if choice == "loyal_program":
        await state.set_state(Order.type)
        await callback.message.edit_caption(caption="Окей, выбери кофе заново 👇", reply_markup=type_cofe_ikb)
        return
    if choice == "use_free_coffee":
        referral_user = await postgres_client.fetchrow("SELECT free_coffees FROM referral_program WHERE user_id=$1",
                                                       user_id)
        if referral_user and referral_user['free_coffees'] > 0:
            await state.update_data(use_free=True)
            summary_text = await build_order_summary(state)
            await callback.message.edit_caption(
                caption=f"✅ Кофе будет бесплатным!\n\n{summary_text}\n\nОсталось подтвердить заказ.",
                reply_markup=get_loyalty_ikb(referral_user['free_coffees'] - 1))
        else:
            await callback.answer("У вас нет бесплатных кофе для списания.", show_alert=True)
        return
    if choice == "create_order":
        await state.set_state(Order.ready)
        data = await state.get_data()
        order_is_free = data.get('use_free', False)
        total_price = calculate_order_total(data)
        order_db_data = {
            'type': data.get('type'),
            'cup': data.get('cup'),
            'syrup': data.get('syrup', 'Без сиропа'),
            'croissant': data.get('croissant', 'Без добавок'),
            'time': data.get('time'),
            'is_free': order_is_free, 'username': callback.from_user.username,
            'user_id': user_id,
            'first_name': callback.from_user.first_name,
            'timestamp': datetime.datetime.now(),
            "total_price": total_price
        }
        new_order_record = await postgres_client.add_order(order_db_data)
        if not new_order_record:
            await callback.answer("Произошла ошибка при создании заказа.", show_alert=True)
            return
        order_id = new_order_record['order_id']
        await state.update_data(last_order_id=order_id)
        if order_is_free:
            caption_text = (f"✅ Ваш заказ №{order_id} на сумму {total_price} Т оформлен (оплачено бонусом)!\n"
                            f"Когда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇")
            await postgres_client.execute(
                "UPDATE referral_program SET free_coffees = free_coffees - 1 WHERE user_id = $1", user_id)
        else:
            caption_text = (f"✅ Ваш заказ №{order_id} на сумму {total_price} Т оформлен!\n"
                            f"Когда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇")
        await callback.message.edit_caption(caption=caption_text, reply_markup=ready_cofe_ikb)
        order_payload = {
            "order_id": order_id,
            "type": new_order_record['type'],
            "cup": new_order_record['cup'],
            "time": new_order_record['time'],
            "status": new_order_record.get('status', 'new'),
            "syrup": new_order_record.get('syrup'),
            "croissant": new_order_record.get('croissant'),
            "is_free": new_order_record.get('is_free', False),
            "timestamp": new_order_record['timestamp'].isoformat(),
            "total_price": total_price
        }
        await ws_manager.broadcast({"type": "new_order", "payload": order_payload})
        referral = await postgres_client.fetchrow(
            "SELECT referrer_id, rewarded FROM referral_links WHERE referred_id=$1", user_id)
        if referral and not referral['rewarded']:
            referrer_id = referral['referrer_id']
            await postgres_client.execute(
                "UPDATE referral_program SET free_coffees = free_coffees + 1, referred_count = referred_count + 1 WHERE user_id=$1",
                referrer_id)
            await postgres_client.execute("UPDATE referral_links SET rewarded = TRUE WHERE referred_id = $1", user_id)
            await callback.bot.send_message(chat_id=referrer_id,
                                            text="🎉 Вам начислен бонус! За то, что ваш друг сделал первый заказ, вы получили один бесплатный кофе.")


# --- Шаг 7: Клиент подошел ---
@router.callback_query(F.data == "cancel_order", Order.ready)
async def cancel_order_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает отмену заказа пользователем.

    Позволяет отменить заказ в течение 3 минут после его создания.
    Обновляет статус заказа в БД на 'cancelled', возвращает списанный
    бонусный кофе (если он был использован) и оповещает WebSocket
    о статусе.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
        state (FSMContext): Контекст состояния FSM.
    """
    data = await state.get_data()
    order_id = data.get('last_order_id')
    if not order_id:
        await callback.answer("Не удалось найти номер вашего заказа.", show_alert=True)
        return

    order_record = await postgres_client.fetchrow("SELECT timestamp FROM orders WHERE order_id = $1", order_id)
    if not order_record:
        await callback.answer("Заказ не найден в системе.", show_alert=True)
        return

    time_created = order_record['timestamp']
    time_now = datetime.datetime.now()
    if time_created.tzinfo:
        time_created = time_created.replace(tzinfo=None)

    if (time_now - time_created).total_seconds() > 180:
        await callback.answer("❌ Прошло более 3 минут, отменить заказ уже нельзя.", show_alert=True)
        # Убираем кнопку отмены, оставляя только "Я подошел"
        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶‍♂️ Я подошел(ла)", callback_data="client_arrived")]
        ]))
        return

    await callback.answer("Заказ отменяется...")
    await postgres_client.update(table="orders", data={"status": "cancelled"}, where="order_id = $1", params=[order_id])
    logger.info(f"Order #{order_id} was cancelled by user.")

    if data.get('use_free', False):
        await postgres_client.execute("UPDATE referral_program SET free_coffees = free_coffees + 1 WHERE user_id = $1",
                                      callback.from_user.id)
        logger.info(f"Returned 1 free coffee to user {callback.from_user.id}")

    await ws_manager.broadcast({"type": "status_update", "payload": {"order_id": order_id, "new_status": "completed"}})

    await callback.message.edit_caption(caption="✅ Ваш заказ был успешно отменен.", reply_markup=None)
    await state.clear()
    await start_msg(message=callback)


@router.callback_query(F.data == "client_arrived", Order.ready)
async def order_ready(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Я подошел(ла)" (шаг 7).

    Изменяет статус заказа на 'arrived' в базе данных, оповещает
    бариста через WebSocket и отправляет ему личное сообщение
    с деталями заказа. После этого очищает состояние и возвращает
    пользователя в главное меню.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
        state (FSMContext): Контекст состояния FSM.
    """
    await callback.message.edit_caption(caption="Отлично, уже несем ваш заказ!",
                                        reply_markup=None)
    data = await state.get_data()
    order_id = data.get('last_order_id')
    if not order_id:
        await callback.message.edit_caption(caption="😕 Не удалось найти номер вашего последнего заказа.",
                                            reply_markup=None)
        await state.clear()
        return
    await postgres_client.update(table="orders", data={"status": "arrived"}, where="order_id = $1", params=[order_id])
    logger.info(f"Order #{order_id} status changed to 'arrived'.")
    await ws_manager.broadcast({"type": "status_update", "payload": {"order_id": order_id, "new_status": "arrived"}})
    admin_summary = await build_order_summary(state)
    total_price = calculate_order_total(data)
    is_free = data.get('use_free', False)
    text_for_admin = f"🚶‍♂️ Клиент подошел - @{callback.from_user.username} (Заказ №{order_id})\n\n{admin_summary}"
    if is_free:
        text_for_admin += "\n\n(Заказ был бесплатным)"
    else:
        text_for_admin += f"\n\n💰 Сумма к оплате: {total_price} Т"
    await callback.bot.send_message(config.BARISTA_ID, text_for_admin)
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ Бариста уведомлен. Ожидайте!",
                                        reply_markup=None)
    await state.clear()
    await start_msg(message=callback)


# --- Кнопка "Хочу Бота" ---
@router.callback_query(F.data == "buy_bot")
async def buy_bot_handler(callback: CallbackQuery):
    """
    Обрабатывает нажатие на кнопку "Хочу Бота".

    Отправляет пользователю уведомление о принятии заявки и пересылает
    контактные данные пользователя администратору.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
    """
    await callback.answer(text="Ваша заявка принята, в ближайшее время наш менеджер с Вами свяжется.", show_alert=True)
    text = f"❗️❗️❗️ Клиент @{callback.from_user.username} хочет купить бота. Свяжись с ним НЕМЕДЛЕННО!!!"
    await callback.bot.send_message(chat_id=config.ADMIN_CHAT_ID, text=text)


# --- Кнопка "Хочу Бота" ---
@router.callback_query(F.data == "test_buy")
async def test_buy_handler(callback: CallbackQuery):
    """
    Обрабатывает тестовую покупку через платежную систему.

    Создает запись о платеже в базе данных, генерирует счет на оплату
    через сервис epay_service и отправляет пользователю ссылку для оплаты.

    Args:
        callback (CallbackQuery): Объект callback-запроса.
    """
    user_id = callback.from_user.id
    amount = 150  # Тестовая сумма в тенге
    description = f"Тестовая покупка от пользователя {user_id}"

    await callback.answer("⏳ Создаем счет на оплату...")

    # --- ИЗМЕНЕННАЯ ЛОГИКА ---
    # 1. Сначала генерируем уникальный ID для платежа здесь, в коде
    payment_id = uuid.uuid4()

    # 2. Теперь вставляем его в базу данных вместе с остальными данными
    try:
        await postgres_client.insert("payments", {
            "payment_id": payment_id,  # <-- Передаем наш сгенерированный ID
            "user_id": user_id,
            "amount": amount,
            "description": description
        })
        logger.info(f"Создана запись о платеже #{payment_id} для пользователя {user_id}")

    except Exception as e:
        logger.error(f"Не удалось создать запись о платеже для {user_id}: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    # 3. Генерируем ссылку на оплату, используя ID, который у нас уже есть
    payment_url = await epay_service.create_invoice(
        amount=amount, payment_id=payment_id, description=description, bot=callback.bot
    )

    # 4. Отправляем ссылку пользователю
    if payment_url:
        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Оплатить {amount} KZT", url=payment_url)]
        ])
        await callback.message.answer(
            f"Ваш счет на оплату готов.", reply_markup=payment_keyboard
        )
    else:
        # Если не удалось создать ссылку, меняем статус в БД на 'error'
        await postgres_client.update("payments", {"status": "error"}, "payment_id = $1", [payment_id])
        await callback.message.answer("Не удалось создать ссылку на оплату. Попробуйте позже.")


# ДОБАВЬТЕ ЭТОТ КОД В САМЫЙ КОНЕЦ ФАЙЛА С ХЭНДЛЕРАМИ

@router.callback_query()  # <-- Обратите внимание: НЕТ фильтров по состоянию или данным
async def catch_unmatched_callbacks(callback: CallbackQuery, state: FSMContext):
    """
    Этот хэндлер-перехватчик сработает на ЛЮБОЙ колбэк,
    который не был пойман другими хэндлерами.
    """
    current_state = await state.get_state()

    logger.error(f"!!! ПОЙМАН НЕОБРАБОТАННЫЙ КОЛБЭК !!!")
    logger.error(f"Пользователь: {callback.from_user.id}")
    logger.error(f"Нажал на кнопку с данными: '{callback.data}'")
    logger.error(f"ТЕКУЩЕЕ СОСТОЯНИЕ ПО ВЕРСИИ FSM: --> {current_state} <--")

    await callback.answer(f"DEBUG: Ваше состояние: {current_state}", show_alert=True)
