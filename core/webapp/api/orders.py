from fastapi import APIRouter, HTTPException
from loguru import logger
from asyncpg import Record
import datetime

from core.utils.database import postgres_client
from core.webapp.ws.orders_ws import manager

# <<< --- РЕШЕНИЕ: ИМПОРТИРУЕМ НАПРЯМУЮ ИЗ BASIC --- >>>
from core.handlers.basic import calculate_order_total

router = APIRouter(prefix="/api/orders", tags=["Orders"])


async def get_all_active_orders_from_db():
    """Получает все заказы, которые еще не завершены И не отменены."""
    query = "SELECT * FROM orders WHERE status NOT IN ('completed', 'cancelled') ORDER BY timestamp ASC"
    try:
        records: list[Record] = await postgres_client.fetch(query)
        orders_with_price = []
        for record in records:
            order_dict = dict(record)
            # Теперь это работает
            order_dict['total_price'] = calculate_order_total(order_dict)
            orders_with_price.append(order_dict)
        return orders_with_price
    except Exception as e:
        logger.error(f"Failed to fetch active orders: {e}")
        return []


@router.get("/completed")
async def get_completed_orders_today():
    """Получает все завершенные заказы за СЕГОДНЯ."""
    query = "SELECT * FROM orders WHERE status = 'completed' AND created_at::date = NOW()::date ORDER BY timestamp DESC"
    try:
        records: list[Record] = await postgres_client.fetch(query)
        orders_with_price = []
        for record in records:
            order_dict = dict(record)
            # И здесь тоже
            order_dict['total_price'] = calculate_order_total(order_dict)
            orders_with_price.append(order_dict)
        return orders_with_price
    except Exception as e:
        logger.error(f"Failed to fetch completed orders: {e}")
        return []


async def update_order_status_in_db(order_id: int, status: str):
    """Обновляет статус конкретного заказа в БД."""
    try:
        await postgres_client.update(
            table="orders",
            data={"status": status},
            where="order_id = $1",
            params=[order_id]
        )
        logger.info(f"Updated order {order_id} to status '{status}' in DB")
        return {"status": "success", "order_id": order_id, "new_status": status}
    except Exception as e:
        logger.error(f"Failed to update order {order_id} status: {e}")
        raise HTTPException(status_code=500, detail="Database update failed")


@router.put("/{order_id}/status")
async def update_order_status(order_id: int, status: str):
    """Этот эндпоинт вызывается, когда бариста нажимает кнопку на карточке заказа."""
    if status not in ["in_progress", "ready", "arrived", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    result = await update_order_status_in_db(order_id, status)

    # Для отмененных заказов тоже отправляем 'completed', чтобы они исчезли с доски
    websocket_status = "completed" if status == "cancelled" else status

    await manager.broadcast({
        "type": "status_update",
        "payload": {"order_id": order_id, "new_status": websocket_status}
    })

    return result
