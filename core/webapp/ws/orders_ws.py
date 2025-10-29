from typing import List
from fastapi import WebSocket
from loguru import logger
import json


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection: {websocket.client}. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected: {websocket.client}. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Отправить сообщение всем подключенным клиентам."""
        disconnected_sockets = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                # Если сокет закрыт, запоминаем его для удаления
                disconnected_sockets.append(connection)

        # Удаляем "мертвые" сокеты
        if disconnected_sockets:
            for socket in disconnected_sockets:
                self.disconnect(socket)

        if self.active_connections:
            logger.info(f"Broadcasted message to {len(self.active_connections)} clients.")


manager = ConnectionManager()
