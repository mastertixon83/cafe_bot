from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from pathlib import Path
import datetime

from core.utils.states import Order
from core.keyboards.inline.inline_menu import (
    mainMenu_ikb, type_cofe_ikb, cup_cofe_ikb, time_cofe_ikb, ready_cofe_ikb,
    get_loyalty_ikb, partners_ikb
)
from core.utils.database import postgres_client
from core.utils.google_sheets_manager import google_sheets_manager

from config import config

router = Router()


async def start_msg(message):
    text = (f"""Привет 👋! Ты в боте кофейни Кофе на ходу. 
    Мы варим кофе с собой и выносим его тебе прямо в руки — без очередей, шума и беготни. 
    Просто выбери напиток, укажи через сколько подойдешь — и всё будет готово к твоему приходу.
    👇Начнем?""")

    path = Path(__file__).resolve().parent.parent.parent / "coffee-cup-fixed.jpg"
    photo = FSInputFile(path)

    await message.answer_photo(
        photo=photo,
        caption=text,
        reply_markup=mainMenu_ikb
    )


# --- /start ---
@router.message(CommandStart(deep_link=True))
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Проверяем, существует ли пользователь в БД
    user = await postgres_client.fetchrow("SELECT * FROM users WHERE telegram_id=$1", user_id)
    if not user:
        await postgres_client.insert("users", {"telegram_id": user_id, "username": username, "first_name": first_name})

    # Обработка реферальной ссылки
    if message.text.startswith("/start ref_"):
        try:
            referrer_id = int(message.text.split('_')[1])
            # Проверяем, что пользователь не перешел по своей же ссылке
            if referrer_id != user_id:
                # Проверяем, не был ли он уже приглашен ранее
                referral = await postgres_client.fetchrow("SELECT * FROM referral_links WHERE referred_id=$1", user_id)
                if not referral:
                    await postgres_client.insert("referral_links", {"referrer_id": referrer_id, "referred_id": user_id})
        except (ValueError, IndexError):
            pass  # Если deep_link неверный, просто игнорируем его

    await start_msg(message=message)


# --- Начало заказа ---
@router.callback_query(F.data == "make_order")
async def handle_text_message(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Order.type)
    await callback.message.edit_caption(
        caption="Какой кофе хочешь сегодня? (Выбери из списка 👇)",
        reply_markup=type_cofe_ikb
    )


# --- Партнерская программа ---
@router.callback_query(F.data == "partners")
async def show_partners_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username

    # Проверяем, есть ли пользователь в таблице партнерской программы
    referral_user = await postgres_client.fetchrow(
        "SELECT free_coffees FROM referral_program WHERE user_id=$1", user_id
    )

    if not referral_user:
        # Если нет, добавляем его с 0 бонусов
        await postgres_client.insert("referral_program", {"user_id": user_id})
        free_coffees = 0
    else:
        free_coffees = referral_user['free_coffees']

    # Формируем реферальную ссылку
    bot_info = await callback.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    text = (
        f"""**Твой бесплатный кофе ждёт!** ✨\n\n
        За каждого друга, который придёт по твоей ссылке и сделает заказ, ты получишь бесплатный кофе.\n Сейчас у тебя **{free_coffees}** бонусов.\n\n
        Поделись своей ссылкой:\n{referral_link}"""
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=partners_ikb
    )


# --- Возврат в главное меню ---
@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    text = (f"""Привет 👋! Ты в боте кофейни Кофе на ходу. 
    Мы варим кофе с собой и выносим его тебе прямо в руки — без очередей, шума и беготни. 
    Просто выбери напиток, укажи через сколько подойдешь — и всё будет готово к твоему приходу.
    👇Начнем?""")

    path = Path(__file__).resolve().parent.parent.parent / "coffee-cup-fixed.jpg"
    photo = FSInputFile(path)

    await callback.message.edit_media(
        media=InputMediaPhoto(media=photo, caption=text),
        reply_markup=mainMenu_ikb
    )


# --- Тип кофе ---
@router.callback_query(Order.type)
async def order_type(callback: CallbackQuery, state: FSMContext):
    choice = callback.data

    if choice == "type_cancel":
        await state.clear()
        await callback.message.edit_caption(caption="❌ Заказ отменён", reply_markup=None)
        await start_msg(message=callback.message)
        return

    await state.update_data(type=choice)
    await state.set_state(Order.cup)

    await callback.message.edit_caption(
        caption="Какой объем подойдет?",
        reply_markup=cup_cofe_ikb
    )


# --- Тара ---
@router.callback_query(Order.cup)
async def order_cup(callback: CallbackQuery, state: FSMContext):
    choice = callback.data

    if choice == "cup_back":
        await state.set_state(Order.type)
        await callback.message.edit_caption(
            caption="Выбери кофе заново 👇",
            reply_markup=type_cofe_ikb
        )
        return

    await state.update_data(cup=choice)
    await state.set_state(Order.time)

    await callback.message.edit_caption(
        caption="Через сколько минут подойдешь за кофе?",
        reply_markup=time_cofe_ikb
    )


# --- Время ---
@router.callback_query(Order.time)
async def order_time(callback: CallbackQuery, state: FSMContext):
    choice = callback.data

    if choice == "time_back":
        await state.set_state(Order.cup)
        await callback.message.edit_caption(
            caption="Выбери объем заново 👇",
            reply_markup=cup_cofe_ikb
        )
        return

    await state.update_data(time=choice)
    data = await state.get_data()
    await state.set_state(Order.confirm)

    # Получаем количество бонусов для динамической клавиатуры
    user_id = callback.from_user.id
    referral_user = await postgres_client.fetchrow(
        "SELECT free_coffees FROM referral_program WHERE user_id=$1", user_id
    )
    free_coffees = referral_user['free_coffees'] if referral_user else 0

    await callback.message.edit_caption(
        caption=(f"""Проверь всё перед отправкой 👇\n\n
☕️ Кофе: {data.get('type')}
📏 Объем: {data.get('cup')} мл
⏱️ Подойдешь через: {data.get('time')} минут

Всё верно?"""),
        reply_markup=get_loyalty_ikb(free_coffees)
    )


# --- Подтверждение ---
@router.callback_query(Order.confirm)
async def order_uproove(callback: CallbackQuery, state: FSMContext):
    choice = callback.data
    data = await state.get_data()
    user_id = callback.from_user.id

    # Кнопка "Изменить"
    if choice == "loyal_program":
        # Просто сбрасываем состояние и возвращаемся к началу
        await state.set_state(Order.type)
        await callback.message.edit_caption(
            caption="Окей, выбери кофе заново 👇",
            reply_markup=type_cofe_ikb
        )
        return

    # Кнопка "Списать бонус"
    if choice == "use_free_coffee":
        referral_user = await postgres_client.fetchrow(
            "SELECT free_coffees FROM referral_program WHERE user_id=$1", user_id
        )
        if referral_user and referral_user['free_coffees'] > 0:
            # НЕ списываем бонус в БД, а просто сохраняем флаг в состоянии FSM
            await state.update_data(use_free=True)
            free_coffees_remaining = referral_user['free_coffees'] - 1

            await callback.message.edit_caption(
                caption="Кофе будет бесплатным! ✅\n\nОсталось подтвердить заказ.",
                reply_markup=get_loyalty_ikb(free_coffees_remaining)
            )
        else:
            await callback.answer("У вас нет бесплатных кофе для списания.", show_alert=True)

        return

    # Кнопка "Подтвердить"
    if choice == "create_order":
        await state.set_state(Order.ready)

        caption_text = "✅ Заказ оформлен!\nКогда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇"
        order_is_free = data.get('use_free', False)

        # # --- Добавляем данные в Google Sheets ---
        # order_data = {
        #     'type': data.get('type'),
        #     'cup': data.get('cup'),
        #     'time': data.get('time'),
        #     'is_free': order_is_free,
        #     'user_id': user_id,
        #     'username': callback.from_user.username,
        #     'first_name': callback.from_user.first_name,
        #     'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # }
        # await google_sheets_manager.add_order(order_data) # Тариф Стандарт
        # ----------------------------------------

        # --- Добавляем данные в PostgreSQL ---
        order_data = {
            'type': data.get('type'),
            'cup': data.get('cup'),
            'time': data.get('time'),
            'is_free': order_is_free,
            'user_id': user_id,
            'username': callback.from_user.username,
            'first_name': callback.from_user.first_name,
            'timestamp': datetime.datetime.now()  # Убираем .strftime
        }
        await postgres_client.add_order(order_data)
        # ----------------------------------------

        if order_is_free:
            caption_text = "✅ Заказ оформлен (бесплатно)!\nКогда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇"

            # ТОЛЬКО ЗДЕСЬ списываем бонус из базы данных
            await postgres_client.execute(
                "UPDATE referral_program SET free_coffees = free_coffees - 1 WHERE user_id = $1",
                user_id
            )

        await callback.message.edit_caption(
            caption=caption_text,
            reply_markup=ready_cofe_ikb
        )

        text_for_admin = (f"""❗️❗️❗️  Новый заказ️  @{callback.from_user.username}❗️❗️❗️
        ☕️ Кофе: {data.get('type')}
        📏 Объем: {data.get('cup')} мл
        ⏱️ Подойдёт через: {data.get('time')} минут
        """)

        if order_is_free:
            text_for_admin = "🎉 БЕСПЛАТНЫЙ ЗАКАЗ 🎉\n" + text_for_admin

        await callback.bot.send_message(chat_id=config.BARISTA_CHAT_ID, text=text_for_admin)

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
                "UPDATE referral_links SET rewarded = TRUE WHERE referred_id = $1",
                user_id
            )

            await callback.bot.send_message(
                chat_id=referrer_id,
                text="🎉 Вам начислен бонус! За то, что ваш друг сделал первый заказ, вы получили один бесплатный кофе. Он уже ждет вас в разделе Пригласи друга."
            )


# --- Клиент подошел ---
@router.callback_query(Order.ready)
async def order_ready(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    text = (f"""Привет 👋! Ты в боте кофейни Кофе на ходу. 
        Мы варим кофе с собой и выносим его тебе прямо в руки — без очередей, шума и беготни. 
        Просто выбери напиток, укажи через сколько подойдешь — и всё будет готово к твоему приходу.
        👇Начнем?""")

    await callback.message.edit_caption(
        caption=text,
        reply_markup=mainMenu_ikb
    )

    text = (f"""Клиент подошел 🚶‍♂️ - @{callback.from_user.username}
☕️ Кофе: {data.get('type')}
📏 Объем: {data.get('cup')} мл
⏱️ Подойдёт через: {data.get('time')} минут
    """)
    # тут можно уведомить бариста (например, в админский чат)
    await callback.bot.send_message(chat_id=config.BARISTA_CHAT_ID, text=text)

    await state.clear()


# Кнопка Хочу Бота
@router.callback_query(F.data == "buy_bot")
async def show_partners_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username

    await callback.message.answer(user_id=user_id,
                                  text="Ваша заявка принята, в ближайшее время наш менеджер с Вами свяжется.")
    text = (f"""Клиент - @{callback.from_user.username}
    Хочет купить бота свяжись с ним НЕМЕДЛЕННО!!!
        """)
    await callback.bot.send_message(chat_id=config.ADMIN_CHAT_ID, text=text)
