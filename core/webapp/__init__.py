from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from loguru import logger

# ИЗМЕНЕНИЕ 1: Импортируем get_all_active_orders_from_db
from .api.orders import router as api_router, get_all_active_orders_from_db
from .ws.orders_ws import manager

# Создаем приложение FastAPI
app = FastAPI(title="Coffee Shop WebApp")

# Пути к статике и шаблонам
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Подключаем роутер API (в нем остались только эндпоинты для обновления статуса и т.д.)
app.include_router(api_router)


# ИЗМЕНЕНИЕ 2: Добавляем новый "бронебойный" эндпоинт для получения заказов
@app.get("/api/orders", include_in_schema=False)
@app.get("/api/orders/")
async def get_active_orders_direct(request: Request):
    """
    Прямая регистрация эндпоинта для обхода проблем с APIRouter.
    """
    logger.info(f"✅✅✅ ПОПАДАНИЕ В ПРЯМОЙ ЭНДПОИНТ: {request.url.path}")
    return await get_all_active_orders_from_db()


# Главная страница доски заказов (остается без изменений)
@app.get("/")
async def get_board(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Эндпоинт для WebSocket (остается без изменений)
@app.websocket("/ws/orders")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Просто держим соединение открытым
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
