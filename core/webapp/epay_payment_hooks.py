# core/webhooks/epay_payment_hooks.py

from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext

from core.utils.database import postgres_client

router = APIRouter()


# --- МОДЕЛЬ ДАННЫХ ---
class EpayWebhook(BaseModel):
    invoice_id: str = Field(..., alias="invoiceId")
    status: str
    amount: int
    currency: str


# --- DEPENDENCIES ДЛЯ ДОСТУПА К BOT И DISPATCHER ---
def get_bot(request: Request) -> Bot:
    if not hasattr(request.app.state, 'bot_instance') or not request.app.state.bot_instance:
        raise HTTPException(status_code=500, detail="Bot instance not available.")
    return request.app.state.bot_instance


def get_dispatcher(request: Request) -> Dispatcher:
    if not hasattr(request.app.state, 'dp') or not request.app.state.dp:
        raise HTTPException(status_code=500, detail="Dispatcher instance not available.")
    return request.app.state.dp


# --- ФОНОВАЯ ЗАДАЧА ДЛЯ ОБРАБОТКИ УСПЕШНОГО ПЛАТЕЖА ---
async def process_successful_payment(payment_id: str, bot: Bot, dp: Dispatcher):
    """
    Выполняется в фоне: находит платеж, создает заказ, уведомляет пользователя.
    """
    from core.handlers.basic import process_and_save_order

    logger.info(f"Начинаем фоновую обработку успешного платежа #{payment_id}")

    # 1. Находим "черновик" платежа в нашей базе
    payment = await postgres_client.fetchrow(
        "SELECT * FROM payments WHERE payment_id = $1 AND status = 'pending'", payment_id
    )
    if not payment:
        logger.warning(f"Фоновая задача: Платеж #{payment_id} не найден или уже обработан.")
        return

    user_id = payment['user_id']
    order_data = payment['order_data']
    amount = payment['amount']

    # 2. Получаем данные о пользователе, чтобы передать их в функцию создания заказа
    user_info = await postgres_client.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", user_id)
    if not user_info:
        logger.error(f"Не удалось найти пользователя {user_id} для создания заказа по платежу #{payment_id}")
        await postgres_client.update("payments", {"status": "error"}, "payment_id = $1", [payment_id])
        return

    # 3. Вызываем нашу универсальную функцию для создания реального заказа
    logger.info(f"Вызов process_and_save_order для платежа #{payment_id}")
    order_record = await process_and_save_order(
        order_data=order_data,
        user_id=user_id,
        username=user_info['username'],
        first_name=user_info['first_name'],
        bot=bot,
        payment_id=payment_id  # Передаем ID платежа для связи
    )

    # 4. Обрабатываем результат
    if order_record:
        # Успех! Обновляем статус платежа и связываем его с созданным заказом
        await postgres_client.update(
            "payments",
            {"status": "paid", "order_id": order_record['order_id']},
            "payment_id = $1",
            [payment_id]
        )
        text = f"✅ Ваша покупка на сумму {amount} KZT прошла успешно! Заказ №{order_record['order_id']} оформлен."

        # Очищаем состояние FSM пользователя, чтобы он мог сделать новый заказ
        storage_key = {'bot_id': bot.id, 'chat_id': user_id, 'user_id': user_id}
        state = FSMContext(storage=dp.storage, key=storage_key)
        await state.clear()
        logger.info(f"Состояние FSM для пользователя {user_id} очищено после успешной оплаты.")
    else:
        # Ошибка! Платеж прошел, но заказ не создался.
        await postgres_client.update("payments", {"status": "error"}, "payment_id = $1", [payment_id])
        text = f"❌ Оплата на сумму {amount} KZT прошла, но произошла ошибка при оформлении заказа. Свяжитесь с поддержкой."

    # 5. Уведомляем пользователя
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление по платежу #{payment_id} пользователю {user_id}: {e}")


# --- ГЛАВНЫЙ ХЕНДЛЕР ВЕБХУКА ---
@router.post("/epay", include_in_schema=False)
async def process_epay_webhook(
        payload: EpayWebhook,
        background_tasks: BackgroundTasks,
        bot: Bot = Depends(get_bot),
        dp: Dispatcher = Depends(get_dispatcher)
):
    logger.info(f"Получен вебхук от Epay: {payload.model_dump_json(indent=2)}")
    payment_id = payload.invoice_id

    # Обновляем статус в любом случае
    await postgres_client.update("payments", {"status": payload.status.lower()}, "payment_id = $1", [payment_id])

    if payload.status.lower() == "paid":
        # Запускаем всю сложную логику в фоне, чтобы мгновенно ответить Epay
        background_tasks.add_task(process_successful_payment, payment_id, bot, dp)
        logger.info(f"Задача для обработки платежа #{payment_id} добавлена в фон.")

    elif payload.status.lower() == "failed":
        # Если платеж не удался, просто уведомляем пользователя
        payment = await postgres_client.fetchrow("SELECT user_id FROM payments WHERE payment_id = $1", payment_id)
        if payment:
            await bot.send_message(payment['user_id'], "❌ Ваша оплата не удалась. Попробуйте снова.")

    return {"status": "ok"}
