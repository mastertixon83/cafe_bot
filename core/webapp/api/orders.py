# core/webapp/api/orders.py (ПОЛНАЯ ВЕРСИЯ С ИЗМЕНЕНИЯМИ)

from fastapi import APIRouter, HTTPException
from loguru import logger
from asyncpg import Record

from core.utils.database import postgres_client
from core.webapp.ws.orders_ws import manager

router = APIRouter(prefix="/api/orders", tags=["Orders"])


async def get_all_active_orders_from_db():
    """Получает все заказы, которые еще не завершены."""
    # Используем 'order_id' вместо 'id' и 'timestamp' вместо 'created_at' для сортировки
    query = "SELECT * FROM orders WHERE status != 'completed' ORDER BY timestamp ASC"
    try:
        records: list[Record] = await postgres_client.fetch(query)
        # asyncpg возвращает список Record, а FastAPI лучше работает со словарями
        return [dict(record) for record in records]
    except Exception as e:
        logger.error(f"Failed to fetch active orders: {e}")
        return []


async def update_order_status_in_db(order_id: int, status: str):
    """Обновляет статус конкретного заказа в БД."""
    try:
        # Используем метод update из вашего postgres_client
        await postgres_client.update(
            table="orders",
            data={"status": status},
            # Указываем правильное имя колонки 'order_id'
            where="order_id = $1",
            params=[order_id]
        )
        logger.info(f"Updated order {order_id} to status '{status}' in DB")
        return {"status": "success", "order_id": order_id, "new_status": status}
    except Exception as e:
        logger.error(f"Failed to update order {order_id} status: {e}")
        raise HTTPException(status_code=500, detail="Database update failed")


# ФУНКЦИЯ get_active_orders ОТСЮДА ПОЛНОСТЬЮ УДАЛЕНА


@router.put("/{order_id}/status")
async def update_order_status(order_id: int, status: str):
    """Этот эндпоинт вызывается, когда бариста нажимает кнопку на карточке заказа."""
    if status not in ["in_progress", "ready", "completed"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    result = await update_order_status_in_db(order_id, status)

    await manager.broadcast({
        "type": "status_update",
        "payload": {"order_id": order_id, "new_status": status}
    })

    return result
