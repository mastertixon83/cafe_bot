# celery_app.py
import sys
import os
from celery import Celery
from config import config

# === Добавляем корень проекта в PYTHONPATH ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# === Создаем экземпляр Celery ===
celery_app = Celery(
    "coffee_bot_tasks",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND
)

# === Настройки Celery ===
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Almaty",
    enable_utc=True,
)

# === Импортируем таски из корня проекта напрямую ===
# Теперь tasks.py лежит в корне, Celery сразу их увидит
import tasks  # noqa: F401
