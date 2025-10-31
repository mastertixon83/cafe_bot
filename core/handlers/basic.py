# =================================================================
#               ИМПОРТЫ И ИНИЦИАЛИЗАЦИЯ
# =================================================================
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto, InlineKeyboardMarkup, \
    InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from pathlib import Path
import datetime
import time
from loguru import logger
import json

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


# =================================================================
#               СЕРВИСНЫЙ СЛОЙ (БИЗНЕС-ЛОГИКА)
# =================================================================

# <-- ИЗМЕНЕНО: Функция теперь принимает order_data (словарь), а не state, и опциональный payment_id
async def process_and_save_order(order_data: dict, user_id: int, username: str, first_name: str, bot,
                                 payment_id: str = None, status: str = 'new') -> dict | None:
    """
    Выполняет всю логику создания заказа: запись в БД, уведомления,
    обновление реферальной программы. Изолирует бизнес-логику от хэндлера.
    """
    try:
        data = order_data  # <-- ИЗМЕНЕНО: Работаем напрямую со словарем
        order_is_free = data.get('use_free', False)
        total_price = calculate_order_total(data)

        # 1. Создаем запись о заказе в БД
        order_db_data = {
            'type': data.get('type'),
            'cup': data.get('cup'),
            'syrup': data.get('syrup', 'Без сиропа'),
            'croissant': data.get('croissant', 'Без добавок'),
            'time': data.get('time'),
            'is_free': order_is_free,
            'username': username,
            'user_id': user_id,
            'first_name': first_name,
            'timestamp': datetime.datetime.now(),
            "total_price": total_price,
            'payment_id': payment_id,
            'status': status,
            'payment_status': 'bonus' if data.get('use_free', False) else ('paid' if payment_id else 'unpaid')
        }
        new_order_record = await postgres_client.add_order(order_db_data)
        if not new_order_record:
            raise Exception("postgres_client.add_order returned None or False")

        order_id = new_order_record['order_id']
        created_at = new_order_record['created_at']

        # 2. Если заказ бесплатный, списываем бонус
        if order_is_free:
            await postgres_client.execute(
                "UPDATE referral_program SET free_coffees = free_coffees - 1 WHERE user_id = $1", user_id)

        # 3. Отправляем уведомление на доску бариста через WebSocket
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
            "total_price": total_price,
            "created_at": created_at.isoformat(),
            "payment_status": new_order_record.get('payment_status', 'unpaid')
        }
        await ws_manager.broadcast({"type": "new_order", "payload": order_payload})

        # 4. Проверяем и награждаем реферера, если это первый заказ
        referral = await postgres_client.fetchrow(
            "SELECT referrer_id, rewarded FROM referral_links WHERE referred_id=$1", user_id)
        if referral and not referral['rewarded']:
            referrer_id = referral['referrer_id']
            await postgres_client.execute(
                "UPDATE referral_program SET free_coffees = free_coffees + 1, referred_count = referred_count + 1 WHERE user_id=$1",
                referrer_id)
            await postgres_client.execute("UPDATE referral_links SET rewarded = TRUE WHERE referred_id = $1", user_id)
            await bot.send_message(chat_id=referrer_id,
                                   text="🎉 Вам начислен бонус! За то, что ваш друг сделал первый заказ, вы получили один бесплатный кофе.")

        # 5. Отправляем подробное уведомление баристе
        try:
            header = f"❗️❗️❗️ <b>Новый заказ №{order_id}</b>"
            client_info = f"👤 <b>Клиент:</b> @{username}" if username else f"👤 <b>Клиент:</b> {first_name}"
            order_details_parts = [
                f"☕️ <b>Напиток:</b> {data.get('type')}", f"📏 <b>Объем:</b> {data.get('cup')} мл",
            ]
            if data.get('syrup') and data.get('syrup') != 'Без сиропа':
                order_details_parts.insert(1, f"🍯 <b>Сироп:</b> {data.get('syrup')}")
            if data.get('croissant') and data.get('croissant') != 'Без добавок':
                order_details_parts.append(f"🥐 <b>Добавка:</b> {data.get('croissant')}")

            order_details_parts.append(f"⏱️ <b>Будет через:</b> {data.get('time')} минут")
            created_time_str = created_at.strftime('%H:%M')
            order_details_parts.append(f"⏱️ <b>Создан:</b> {created_time_str}")
            order_details = "\n".join(order_details_parts)

            # Информация об оплате
            payment_status = new_order_record.get('payment_status')
            if payment_status == 'paid':
                payment_info = f"✅ <b>ОПЛАЧЕНО ОНЛАЙН:</b> {total_price} Т"
            elif payment_status == 'bonus':
                payment_info = "🎁 <b>ОПЛАЧЕНО БОНУСОМ</b>"
            else:  # unpaid
                payment_info = f"💰 <b>НЕ ОПЛАЧЕНО (оплата на месте):</b> {total_price} Т"
            text_for_barista = f"{header}\n{client_info}\n\n{order_details}\n\n{payment_info}"

            await bot.send_message(chat_id=config.BARISTA_ID, text=text_for_barista, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send detailed notification to barista for order #{order_id}: {e}")
            await bot.send_message(chat_id=config.BARISTA_ID,
                                   text=f"❗️Новый заказ №{order_id}. Не удалось загрузить детали.")

        return new_order_record

    except Exception as e:
        logger.error(f"Critical error in process_and_save_order for user {user_id}: {e}", exc_info=True)
        return None


# =================================================================
#                       ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =================================================================

async def build_order_summary(state: FSMContext) -> str:
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
    await state.update_data(
        free_coffees_count=free_coffees,
        last_callback=callback.model_dump(mode='json')
    )
    await callback.message.edit_caption(caption=caption_with_price, reply_markup=get_loyalty_ikb(free_coffees))


async def start_msg(message: Message | CallbackQuery):
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


# =================================================================
#                       ОСНОВНЫЕ ХЭНДЛЕРЫ
# =================================================================

@router.message(CommandStart(deep_link=True))
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
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


# =================================================================
#                       ШАГИ ЗАКАЗА (FSM)
# =================================================================

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


# =================================================================
#      ШАГ 6: ПОДТВЕРЖДЕНИЕ ЗАКАЗА И ОПЛАТА
# =================================================================

@router.callback_query(Order.confirm, F.data == "create_order")
async def confirm_create_order(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает подтверждение заказа БЕЗ ОПЛАТЫ (например, за бонусы).
    """
    await callback.answer("⏳ Минуточку, оформляем ваш заказ...", show_alert=False)
    await callback.message.edit_reply_markup(reply_markup=None)

    # <-- ИЗМЕНЕНО: Получаем данные и передаем в рефакторенную функцию
    order_data = await state.get_data()
    order_record = await process_and_save_order(
        order_data=order_data,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        bot=callback.bot
    )

    if order_record:
        order_id = order_record['order_id']
        total_price = order_record['total_price']
        await state.set_state(Order.ready)
        await state.update_data(last_order_id=order_id)
        caption_text = (f"✅ Ваш заказ №{order_id} на сумму {total_price} Т оформлен!\n"
                        f"Когда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇")
        if order_record['is_free']:
            caption_text = (f"✅ Ваш заказ №{order_id} оформлен (оплачено бонусом)!\n"
                            f"Когда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇")
        await callback.message.edit_caption(caption=caption_text, reply_markup=ready_cofe_ikb)
    else:
        data = await state.get_data()
        free_coffees = data.get('free_coffees_count', 0)
        await callback.message.edit_caption(
            caption="❌ Произошла ошибка при создании заказа.\n\nПожалуйста, попробуйте подтвердить его еще раз.",
            reply_markup=get_loyalty_ikb(free_coffees)
        )


@router.callback_query(Order.confirm, F.data == "pay_order")
async def pay_order_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Оплатить".
    Сохраняет детали заказа в таблицу payments и инициирует оплату.
    """
    user_id = callback.from_user.id
    order_data = await state.get_data()
    amount = calculate_order_total(order_data)

    summary_parts = [f"Кофе: {order_data.get('type')}"]
    if order_data.get('syrup') and order_data.get('syrup') != 'Без сиропа': summary_parts.append(
        f"Сироп: {order_data.get('syrup')}")
    if order_data.get('croissant') and order_data.get('croissant') != 'Без добавок': summary_parts.append(
        f"Добавка: {order_data.get('croissant')}")
    description = f"Оплата заказа: {', '.join(summary_parts)}"

    await callback.answer("⏳ Создаем счет на оплату...")
    payment_id = str(int(time.time() * 1000))

    try:
        await postgres_client.insert("payments", {
            "payment_id": payment_id, "user_id": user_id, "amount": amount,
            "description": description,
            "order_data": json.dumps(order_data, ensure_ascii=False)
        })
        logger.info(f"Создана запись о платеже #{payment_id} для пользователя {user_id} с деталями заказа.")
    except Exception as e:
        logger.error(f"Не удалось создать запись о платеже для {user_id}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при создании счета. Пожалуйста, попробуйте позже.")
        return

    payment_url = await epay_service.create_invoice(
        amount=amount, payment_id=payment_id, description=description, bot=callback.bot
    )

    if payment_url:
        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Оплатить {amount} KZT", url=payment_url)]
        ])
        await callback.message.answer(
            f"Ваш счет на оплату готов.", reply_markup=payment_keyboard
        )
    else:
        await postgres_client.update("payments", {"status": "error"}, "payment_id = $1", [payment_id])
        await callback.message.answer("Не удалось создать ссылку на оплату. Попробуйте позже.")


@router.callback_query(Order.confirm, F.data == "use_free_coffee")
async def confirm_use_free_coffee(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    referral_user = await postgres_client.fetchrow("SELECT free_coffees FROM referral_program WHERE user_id=$1",
                                                   user_id)
    free_coffees = referral_user['free_coffees'] if referral_user else 0

    if free_coffees > 0:
        await callback.answer("✅ Бонус применен!", show_alert=False)
        await state.update_data(use_free=True)
        summary_text = await build_order_summary(state)
        await callback.message.edit_caption(
            caption=f"✅ Кофе будет бесплатным!\n\n{summary_text}\n\nОсталось подтвердить заказ.",
            reply_markup=get_loyalty_ikb(free_coffees - 1)
        )
    else:
        await callback.answer("У вас нет бесплатных кофе для списания.", show_alert=True)


@router.callback_query(Order.confirm, F.data == "loyal_program")
async def confirm_back_to_type(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Order.type)
    await callback.message.edit_caption(caption="Окей, выбери кофе заново 👇", reply_markup=type_cofe_ikb)


# =================================================================
#                       ШАГ 7: КЛИЕНТ ПОДОШЕЛ
# =================================================================

@router.callback_query(Order.ready, F.data == "cancel_order")
async def cancel_order_handler(callback: CallbackQuery, state: FSMContext):
    try:
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
        if time_created.tzinfo:
            time_created = time_created.replace(tzinfo=None)

        if (datetime.datetime.now() - time_created).total_seconds() > 180:
            await callback.answer("❌ Прошло более 3 минут, отменить заказ уже нельзя.", show_alert=True)
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚶‍♂️ Я подошел(ла)", callback_data="client_arrived")]
            ]))
            return

        await callback.answer("Заказ отменяется...")
        await postgres_client.update(table="orders", data={"status": "cancelled"}, where="order_id = $1",
                                     params=[order_id])
        logger.info(f"Order #{order_id} was cancelled by user.")

        if data.get('use_free', False):
            await postgres_client.execute(
                "UPDATE referral_program SET free_coffees = free_coffees + 1 WHERE user_id = $1",
                callback.from_user.id)
            logger.info(f"Returned 1 free coffee to user {callback.from_user.id}")

        await ws_manager.broadcast(
            {"type": "status_update", "payload": {"order_id": order_id, "new_status": "cancelled"}})
        await callback.message.edit_caption(caption="✅ Ваш заказ был успешно отменен.", reply_markup=None)
        await state.clear()

    except Exception as e:
        logger.error(f"Error in cancel_order_handler for user {callback.from_user.id}: {e}")
        await callback.answer("Произошла ошибка при отмене заказа.", show_alert=True)


@router.callback_query(Order.ready, F.data == "client_arrived")
async def order_ready(callback: CallbackQuery, state: FSMContext):
    """
    ФИНАЛЬНАЯ ВЕРСИЯ.
    Обрабатывает нажатие "Я подошел(ла)", берет данные из БД и шлет баристе правильное уведомление.
    """
    try:
        data = await state.get_data()
        order_id = data.get('last_order_id')
        if not order_id:
            await callback.answer("Не удалось найти номер вашего заказа.", show_alert=True)
            await callback.message.delete()
            await start_msg(callback.message)
            return

        await callback.answer("Отлично, бариста уведомлен!", show_alert=False)

        # ----- ВОТ ГЛАВНОЕ ИСПРАВЛЕНИЕ -----
        # 1. Получаем АКТУАЛЬНЫЕ данные о заказе из базы данных
        order_record = await postgres_client.fetchrow("SELECT * FROM orders WHERE order_id = $1", order_id)
        if not order_record:
            logger.warning(
                f"Пользователь {callback.from_user.id} нажал 'Я подошел', но заказ #{order_id} не найден в БД.")
            await callback.message.delete()
            await start_msg(callback.message)
            return

        # 2. Обновляем статус в БД
        await postgres_client.update(table="orders", data={"status": "arrived"}, where="order_id = $1",
                                     params=[order_id])
        logger.info(f"Order #{order_id} status changed to 'arrived'.")

        # 3. Уведомляем WebSocket
        await ws_manager.broadcast(
            {"type": "status_update", "payload": {"order_id": order_id, "new_status": "arrived"}})

        # 4. Формируем ПРАВИЛЬНОЕ сообщение для баристы на основе данных из БД
        order_details_parts = [
            f"☕️ Напиток: {order_record.get('type')}",
            f"📏 Объем: {order_record.get('cup')} мл",
        ]
        if order_record.get('syrup') and order_record.get('syrup') != 'Без сиропа':
            order_details_parts.insert(1, f"🍯 Сироп: {order_record.get('syrup')}")
        if order_record.get('croissant') and order_record.get('croissant') != 'Без добавок':
            order_details_parts.append(f"🥐 Добавка: {order_record.get('croissant')}")

        order_details = "\n".join(order_details_parts)

        payment_status = order_record.get('payment_status')
        total_price = order_record.get('total_price')

        if payment_status == 'paid':
            payment_info = f"✅ <b>ОПЛАЧЕНО ОНЛАЙН</b>"
        elif payment_status == 'bonus':
            payment_info = "🎁 <b>ОПЛАЧЕНО БОНУСОМ</b>"
        else:  # unpaid
            payment_info = f"💰 <b>ОПЛАТА НА МЕСТЕ: {total_price} Т</b>"

        text_for_admin = (f"🚶‍♂️ <b>Клиент подошел!</b> (Заказ №{order_id})\n"
                          f"@{callback.from_user.username}\n\n"
                          f"{order_details}\n\n"
                          f"{payment_info}")

        await callback.bot.send_message(config.BARISTA_ID, text_for_admin, parse_mode="HTML")
        # ------------------------------------

        await callback.message.delete()
        await start_msg(callback.message)

    except Exception as e:
        logger.error(f"Error in order_ready for user {callback.from_user.id}: {e}", exc_info=True)
        await callback.answer("Произошла ошибка, но мы уже уведомили бариста!", show_alert=True)
    finally:
        await state.clear()


# =================================================================
#                       ПРОЧИЕ ХЭНДЛЕРЫ
# =================================================================

@router.callback_query(F.data == "buy_bot")
async def buy_bot_handler(callback: CallbackQuery):
    await callback.answer(text="Ваша заявка принята, в ближайшее время наш менеджер с Вами свяжется.", show_alert=True)
    text = f"❗️❗️❗️ Клиент @{callback.from_user.username} хочет купить бота. Свяжись с ним НЕМЕДЛЕННО!!!"
    await callback.bot.send_message(chat_id=config.ADMIN_CHAT_ID, text=text)


# <-- ИЗМЕНЕНО: Это теперь хендлер для тестовой кнопки из главного меню
@router.callback_query(F.data == "test_buy")
async def test_buy_handler(callback: CallbackQuery):
    """
    Обрабатывает ТЕСТОВУЮ покупку через платежную систему из главного меню.
    """
    user_id = callback.from_user.id
    amount = 150  # Фиксированная сумма для теста
    description = f"Тестовая покупка от пользователя {user_id}"

    await callback.answer("⏳ Создаем тестовый счет на оплату...")

    payment_id = str(int(time.time() * 1000))

    try:
        # Для простого теста можно не сохранять детали заказа в order_data
        await postgres_client.insert("payments", {
            "payment_id": payment_id, "user_id": user_id, "amount": amount, "description": description
        })
        logger.info(f"Создана запись о тестовом платеже #{payment_id} для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Не удалось создать запись о тестовом платеже для {user_id}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        return

    payment_url = await epay_service.create_invoice(
        amount=amount, payment_id=payment_id, description=description, bot=callback.bot
    )

    if payment_url:
        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Оплатить {amount} KZT", url=payment_url)]
        ])
        await callback.message.answer(
            f"Ваш тестовый счет на оплату готов.", reply_markup=payment_keyboard
        )
    else:
        await postgres_client.update("payments", {"status": "error"}, "payment_id = $1", [payment_id])
        await callback.message.answer("Не удалось создать ссылку на оплату. Попробуйте позже.")
