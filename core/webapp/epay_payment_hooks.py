# core/webhooks/epay_payment_hooks.py

from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
import json
from aiogram.fsm.storage.base import StorageKey
from typing import Optional

from core.utils.database import postgres_client
from config import config  # <-- ИЗМЕНЕНО: Добавлен импорт конфига

router = APIRouter()


class EpayWebhook(BaseModel):
    """Pydantic-модель, полностью соответствующая реальным вебхукам от Epay."""
    invoiceId: str
    code: str
    amount: int
    currency: str
    accountId: Optional[str] = None
    amount_bonus: Optional[int] = None
    approvalCode: Optional[str] = None
    cardId: Optional[str] = None
    cardMask: Optional[str] = None
    cardType: Optional[str] = None
    dateTime: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    id: Optional[str] = None
    ip: Optional[str] = None
    ipCity: Optional[str] = None
    ipCountry: Optional[str] = None
    issuer: Optional[str] = None
    language: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    reason: Optional[str] = None
    reasonCode: Optional[int] = None
    reference: Optional[str] = None
    secure: Optional[str] = None
    terminal: Optional[str] = None


def get_bot(request: Request) -> Bot:
    """FastAPI зависимость для получения экземпляра Bot из состояния приложения."""
    if not hasattr(request.app.state, 'bot_instance') or not request.app.state.bot_instance:
        raise HTTPException(status_code=500, detail="Bot instance not available.")
    return request.app.state.bot_instance


def get_dispatcher(request: Request) -> Dispatcher:
    """FastAPI зависимость для получения экземпляра Dispatcher из состояния приложения."""
    if not hasattr(request.app.state, 'dp') or not request.app.state.dp:
        raise HTTPException(status_code=500, detail="Dispatcher instance not available.")
    return request.app.state.dp


async def process_successful_payment(payment_id: str, bot: Bot, dp: Dispatcher):
    """
    Фоновая задача, обрабатывающая успешный платеж.
    """
    # Импортируем здесь, чтобы избежать циклических зависимостей
    from core.handlers.basic import process_and_save_order, format_barista_notification
    from core.keyboards.inline.inline_menu import ready_cofe_ikb
    from core.utils.states import Order

    logger.info(f"Начинаем фоновую обработку успешного платежа #{payment_id}")

    payment = await postgres_client.fetchrow(
        "SELECT * FROM payments WHERE payment_id = $1 AND status = 'pending'", payment_id
    )
    if not payment:
        logger.warning(f"Фоновая задача: Платеж #{payment_id} не найден или уже обработан.")
        return

    user_id = payment['user_id']
    order_data = json.loads(payment['order_data'])
    amount = payment['amount']

    user_info = await postgres_client.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", user_id)
    if not user_info:
        logger.error(f"Не удалось найти пользователя {user_id} для обработки платежа #{payment_id}")
        await postgres_client.update("payments", {"status": "error"}, "payment_id = $1", [payment_id])
        return

    # <--- ИЗМЕНЕНИЕ: Убираем 'bot=bot' и сохраняем результат ---
    result = await process_and_save_order(
        order_data=order_data,
        user_id=user_id,
        username=user_info['username'],
        first_name=user_info['first_name'],
        payment_id=payment_id,
        status='new'
    )

    storage_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    state = FSMContext(storage=dp.storage, key=storage_key)
    state_data = await state.get_data()

    if result:
        order_record = result['order_record']
        notification_info = result['notification_info']
        order_id = order_record['order_id']

        await postgres_client.update(
            "payments", {"status": "paid", "order_id": order_id}, "payment_id = $1", [payment_id]
        )

        # <--- ИЗМЕНЕНИЕ: Отправляем уведомления отсюда ---
        try:
            barista_text = format_barista_notification(order_record, user_info['username'], user_info['first_name'])
            await bot.send_message(chat_id=config.BARISTA_ID, text=barista_text, parse_mode="HTML")

            if 'referrer_id' in notification_info:
                referrer_id = notification_info['referrer_id']
                await bot.send_message(
                    chat_id=referrer_id,
                    text="🎉 Вам начислен бонус! За то, что ваш друг сделал первый заказ, вы получили один бесплатный кофе."
                )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомления для оплаченного заказа #{order_id}: {e}")

        # Обновляем сообщение у пользователя
        try:
            last_callback_query = state_data.get('last_callback')
            if last_callback_query:
                caption_text = (f"✅ Ваш заказ №{order_id} на сумму {amount} Т успешно оплачен!\n"
                                f"Когда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇")
                await bot.edit_message_caption(
                    chat_id=user_id, message_id=last_callback_query['message']['message_id'],
                    caption=caption_text, reply_markup=ready_cofe_ikb
                )
                logger.info(f"Сообщение для заказа #{order_id} успешно отредактировано.")
            else:
                raise ValueError("Не найден last_callback в состоянии FSM")
        except Exception as e:
            logger.error(f"Не удалось отредактировать сообщение после оплаты: {e}. Отправляем новое.")
            text = f"✅ Ваша покупка прошла успешно! Заказ №{order_id} оформлен."
            await bot.send_message(chat_id=user_id, text=text)

        # Удаляем сообщение со ссылкой на оплату
        try:
            payment_message_id = state_data.get('payment_message_id')
            if payment_message_id:
                await bot.delete_message(chat_id=user_id, message_id=payment_message_id)
                logger.info(f"Сообщение со ссылкой на оплату ({payment_message_id}) удалено.")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение со ссылкой на оплату: {e}")

        await state.set_state(Order.ready)
        await state.update_data(last_order_id=order_id)
        logger.info(f"Пользователь {user_id} переведен в состояние Order.ready для заказа #{order_id}.")
    else:
        await postgres_client.update("payments", {"status": "error"}, "payment_id = $1", [payment_id])
        text = f"❌ Оплата прошла, но произошла ошибка при оформлении заказа. Свяжитесь с поддержкой."
        await bot.send_message(chat_id=user_id, text=text)


@router.post("/epay", include_in_schema=False)
async def process_epay_webhook(
        payload: EpayWebhook,
        background_tasks: BackgroundTasks,
        bot: Bot = Depends(get_bot),
        dp: Dispatcher = Depends(get_dispatcher)
):
    """
    Основной эндпоинт для приема вебхуков от Epay.
    Работает с реальной структурой данных.
    """
    logger.info(f"Получен вебхук от Epay: {payload.model_dump_json(indent=2)}")
    payment_id = payload.invoiceId

    if payload.code.lower() == "ok":
        background_tasks.add_task(process_successful_payment, payment_id, bot, dp)
        logger.info(f"Задача для обработки успешного платежа #{payment_id} добавлена в фон.")

    else:
        logger.warning(f"Получен вебхук о НЕУСПЕШНОЙ оплате #{payment_id}. "
                       f"Статус: '{payload.code}'. Причина: {payload.reason} (Код: {payload.reasonCode})")

        await postgres_client.update("payments", {"status": "failed"}, "payment_id = $1", [payment_id])
        payment = await postgres_client.fetchrow("SELECT user_id FROM payments WHERE payment_id = $1", payment_id)
        if not payment:
            logger.warning(f"Получен failed-вебхук для платежа #{payment_id}, но сам платеж не найден.")
            return {"status": "ok"}

        user_id = payment['user_id']
        storage_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
        state = FSMContext(storage=dp.storage, key=storage_key)
        state_data = await state.get_data()

        try:
            payment_message_id = state_data.get('payment_message_id')
            if payment_message_id:
                await bot.delete_message(chat_id=user_id, message_id=payment_message_id)
                logger.info(f"Сообщение со ссылкой на неудавшийся платеж ({payment_message_id}) удалено.")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение со ссылкой на оплату при failed-статусе: {e}")

        await bot.send_message(user_id, f"❌ Ваша оплата не удалась. Причина: {payload.reason or 'Неизвестная ошибка'}.")

    return {"status": "ok"}
