# core/webhooks/epay_payment_hooks.py

from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
import json
from aiogram.fsm.storage.base import StorageKey

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
    ФИНАЛЬНАЯ ВЕРСИЯ.
    Создает заказ, обновляет сообщение и ПРАВИЛЬНО переводит пользователя в следующее состояние.
    """
    from core.handlers.basic import process_and_save_order
    from core.keyboards.inline.inline_menu import ready_cofe_ikb
    from core.utils.states import Order  # <-- ДОБАВЬ ЭТОТ ИМПОРТ
    import json

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
        # ... (обработка ошибки)
        return

    order_record = await process_and_save_order(
        order_data=order_data, user_id=user_id, username=user_info['username'],
        first_name=user_info['first_name'], bot=bot, payment_id=payment_id, status='new'
    )

    storage_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    state = FSMContext(storage=dp.storage, key=storage_key)
    state_data = await state.get_data()

    if order_record:
        await postgres_client.update(
            "payments", {"status": "paid", "order_id": order_record['order_id']}, "payment_id = $1", [payment_id]
        )
        order_id = order_record['order_id']

        try:
            last_callback_query = state_data.get('last_callback')
            if last_callback_query:
                caption_text = (f"✅ Ваш заказ №{order_id} на сумму {amount} Т успешно оплачен!\n"
                                f"Когда будешь у входа — нажми кнопку ниже, и мы вынесем напиток 👇")
                await bot.edit_message_caption(
                    chat_id=user_id,
                    message_id=last_callback_query['message']['message_id'],
                    caption=caption_text,
                    reply_markup=ready_cofe_ikb
                )
                logger.info(f"Сообщение для заказа #{order_id} успешно отредактировано.")
            else:
                raise ValueError("Не найден last_callback")
        except Exception as e:
            logger.error(f"Не удалось отредактировать сообщение после оплаты: {e}. Отправляем новое.")
            text = f"✅ Ваша покупка прошла успешно! Заказ №{order_id} оформлен."
            await bot.send_message(chat_id=user_id, text=text)

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
        # ------------------------------------
    else:
        await postgres_client.update("payments", {"status": "error"}, "payment_id = $1", [payment_id])
        text = f"❌ Оплата прошла, но произошла ошибка при оформлении заказа. Свяжитесь с поддержкой."
        await bot.send_message(chat_id=user_id, text=text)


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

    # ----- СТРОКА ОБНОВЛЕНИЯ СТАТУСА УДАЛЕНА ОТСЮДА -----

    if payload.status.lower() == "paid":
        background_tasks.add_task(process_successful_payment, payment_id, bot, dp)
        logger.info(f"Задача для обработки платежа #{payment_id} добавлена в фон.")

    elif payload.status.lower() == "failed":
        await postgres_client.update("payments", {"status": "failed"}, "payment_id = $1", [payment_id])
        payment = await postgres_client.fetchrow("SELECT user_id FROM payments WHERE payment_id = $1", payment_id)
        if payment:
            await bot.send_message(payment['user_id'], "❌ Ваша оплата не удалась. Попробуйте снова.")

    return {"status": "ok"}
