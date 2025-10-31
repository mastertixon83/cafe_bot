from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from aiogram import Bot
import uuid

from core.utils.database import postgres_client

router = APIRouter()


class EpayWebhook(BaseModel):
    invoice_id: uuid.UUID = Field(..., alias="invoiceId")
    status: str
    amount: int
    currency: str


def get_bot(request: Request) -> Bot:
    if not hasattr(request.app.state, 'bot_instance') or not request.app.state.bot_instance:
        raise HTTPException(status_code=500, detail="Bot instance not available in app state.")
    return request.app.state.bot_instance


@router.post("/epay", include_in_schema=False)
async def process_epay_webhook(payload: EpayWebhook, bot: Bot = Depends(get_bot)):
    logger.info(f"Получен вебхук от Epay: {payload.model_dump_json(indent=2)}")

    payment_id = payload.invoice_id
    new_status = payload.status.lower()

    payment = await postgres_client.fetchrow("SELECT * FROM payments WHERE payment_id = $1", payment_id)
    if not payment:
        logger.warning(f"Получен вебхук для неизвестного платежа #{payment_id}")
        return {"status": "error", "message": "Payment not found"}

    if payment['status'] in ['paid', 'failed']:
        logger.info(f"Статус платежа #{payment_id} уже финальный: {payment['status']}. Игнорируем.")
        return {"status": "ok", "message": "Already processed"}

    await postgres_client.update("payments", {"status": new_status}, "payment_id = $1", [payment_id])
    user_id = payment['user_id']

    if new_status == "paid":
        text = f"✅ Ваша тестовая покупка на сумму {payload.amount} {payload.currency} прошла успешно!"
    elif new_status == "failed":
        text = f"❌ Оплата на сумму {payload.amount} {payload.currency} не удалась. Попробуйте снова."
    else:
        text = f"ℹ️ Статус вашего платежа #{payment_id[:8]} изменен на: {new_status}"

    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление по платежу #{payment_id} пользователю {user_id}: {e}")

    return {"status": "ok"}
