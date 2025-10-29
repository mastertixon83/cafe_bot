from fastapi import APIRouter, HTTPException
from core.utils.database import postgres_client  # Импортируем ваш клиент БД

router = APIRouter(prefix="/api/orders", tags=["Orders"])


# ПРИМЕР: Вам нужно будет реализовать эти функции на основе вашей БД
async def get_all_active_orders_from_db():
    # Здесь ваш код для получения заказов из PostgreSQL
    # Например: return await postgres_client.pool.fetch("SELECT * FROM orders WHERE status != 'completed'")
    # Пока вернем моковые данные
    return [
        {"id": 1, "drink": "Капучино", "cup": "Своя кружка", "time_to_come": "5 мин", "status": "new"},
        {"id": 2, "drink": "Латте", "cup": "Большой", "time_to_come": "10 мин", "status": "in_progress"},
    ]


async def update_order_status_in_db(order_id: int, status: str):
    # Здесь ваш код для обновления статуса заказа в БД
    # Например: await postgres_client.pool.execute("UPDATE orders SET status=$1 WHERE id=$2", status, order_id)
    logger.info(f"Updating order {order_id} to status {status}")
    return {"status": "success", "order_id": order_id, "new_status": status}


@router.get("/")
async def get_active_orders():
    orders = await get_all_active_orders_from_db()
    return orders


@router.put("/{order_id}/status")
async def update_order_status(order_id: int, status: str):
    # В реальном приложении нужна валидация статуса
    if status not in ["in_progress", "ready", "completed"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    result = await update_order_status_in_db(order_id, status)

    # Оповещаем всех бариста через WebSocket об изменении статуса
    await manager.broadcast({
        "type": "status_update",
        "payload": {"order_id": order_id, "new_status": status}
    })

    return result
