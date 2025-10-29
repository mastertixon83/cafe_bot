from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from loguru import logger

from .api.orders import router as api_router
from .ws.orders_ws import manager

# Создаем приложение FastAPI
app = FastAPI(title="Coffee Shop WebApp")

# Пути к статике и шаблонам
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Подключаем роутер API
app.include_router(api_router)


# Главная страница доски заказов
@app.get("/")
async def get_board(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Эндпоинт для WebSocket
@app.websocket("/ws/orders")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Просто держим соединение открытым
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
