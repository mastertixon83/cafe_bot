# main.py (ПОЛНАЯ ОБНОВЛЕННАЯ ВЕРСИЯ)

from loguru import logger
import traceback
import asyncio
import sys
from typing import Optional
from contextlib import asynccontextmanager

# НОВЫЕ ИМПОРТЫ для веб-сервера
import uvicorn
from fastapi import FastAPI

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# Импортируем роутеры
from core.handlers.basic import router as basic_router
from core.handlers.admin_handlers import router as admin_router
from core.handlers.barista_handlers import router as barista_router  # <-- ДОБАВЛЕНО

# Импортируем утилиты
from core.utils.database import postgres_client
from config import config

# Импортируем наше созданное FastAPI приложение
from core.webapp import app as fastapi_app


class BotApplication:
    """
    Класс для управления жизненным циклом бота.
    Теперь он не управляет запуском процесса, а только своими компонентами.
    """

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.storage = MemoryStorage()
        self.dp: Optional[Dispatcher] = None
        logger.info("BotApplication instance created")

    async def initialize(self) -> None:
        """Асинхронная инициализация всех компонентов бота."""
        try:
            logger.info("Initializing bot components...")

            # Telegram Bot
            self.bot = Bot(
                token=config.TELEGRAM_BOT_TOKEN,
                default=DefaultBotProperties(parse_mode="HTML")
            )
            logger.info("✅ Telegram bot initialized successfully")

            # Dispatcher
            self.dp = Dispatcher(storage=self.storage)
            # Подключаем все роутеры
            self.dp.include_router(basic_router)
            self.dp.include_router(admin_router)
            self.dp.include_router(barista_router)  # <-- ДОБАВЛЕНО
            logger.info("✅ Dispatcher initialized successfully")

            # Lifecycle hooks
            self.dp.startup.register(self._on_startup)
            self.dp.shutdown.register(self._on_shutdown)
            logger.info("✅ Lifecycle handlers registered")

            # PostgreSQL
            await postgres_client.initialize()
            logger.info("✅ PostgreSQL client initialized successfully")

            logger.info("🚀 All bot components initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize bot components: {e}")
            await self.cleanup()
            raise

    async def start_polling(self) -> None:
        """Запускает поллинг бота."""
        if not self.bot or not self.dp:
            raise RuntimeError("Bot or Dispatcher not initialized")
        logger.info("🚀 Starting bot polling...")
        await self.dp.start_polling(self.bot, allowed_updates=["message", "callback_query"])

    async def stop_polling(self) -> None:
        """Останавливает поллинг и закрывает хранилище."""
        if not self.dp:
            return
        logger.info("🛑 Stopping bot polling...")
        await self.dp.storage.close()
        logger.info("✅ Bot polling stopped")

    async def cleanup(self) -> None:
        """Освобождение всех ресурсов."""
        logger.info("🧹 Starting bot cleanup process...")

        # Безопасное закрытие PostgreSQL пула
        try:
            if postgres_client and getattr(postgres_client, "pool", None):
                await postgres_client.close()
                logger.info("✅ PostgreSQL pool closed successfully")
        except Exception as e:
            logger.error(f"❌ Error while closing PostgreSQL pool: {e}")

        # Безопасное закрытие сессии бота
        try:
            if self.bot and self.bot.session and not self.bot.session.closed:
                await self.bot.session.close()
                logger.info("✅ Bot session closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing bot session: {e}")

        logger.info("🧹 Bot cleanup finished successfully")

    # Вспомогательные методы _on_startup и _on_shutdown остаются без изменений
    async def _on_startup(self, bot: Bot) -> None:
        startup_message = "🚀 Бот запущен и готов к работе!"
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, startup_message)
            logger.info("✅ Startup notification sent to admin")
        except Exception as e:
            logger.error(f"❌ Failed to send startup notification: {e}")
        logger.info(startup_message)

    async def _on_shutdown(self, bot: Bot) -> None:
        shutdown_message = "🛑 Бот остановлен."
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, shutdown_message)
            logger.info("✅ Shutdown notification sent to admin")
        except Exception as e:
            logger.error(f"❌ Failed to send shutdown notification: {e}")
        logger.info(shutdown_message)

    # МЕТОДЫ run, _setup_signal_handlers, _trigger_shutdown УДАЛЕНЫ
    # так как теперь жизненным циклом и обработкой сигналов (Ctrl+C)
    # управляет веб-сервер Uvicorn.


# --- ИНТЕГРАЦИЯ С FASTAPI ---

# Создаем единственный экземпляр нашего класса для управления ботом
bot_app = BotApplication()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер FastAPI, который управляет жизненным циклом
    нашего приложения. Он запускает бота при старте сервера и
    корректно останавливает его при завершении работы сервера.
    """
    # --- Код при старте сервера ---
    logger.info("🚀 Starting application lifespan...")

    # Инициализируем компоненты бота (БД, роутеры и т.д.)
    await bot_app.initialize()

    # Запускаем поллинг бота в фоновой задаче
    polling_task = asyncio.create_task(bot_app.start_polling())
    logger.info("Bot polling has been scheduled to run in the background.")

    # Сервер готов к работе
    yield

    # --- Код при остановке сервера (после Ctrl+C) ---
    logger.info("🧹 Shutting down application lifespan...")

    # Отменяем задачу поллинга
    if not polling_task.done():
        logger.info("Cancelling polling task...")
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            logger.info("✅ Polling task cancelled successfully")

    # Корректно останавливаем компоненты бота
    await bot_app.stop_polling()

    # Выполняем очистку ресурсов (закрытие сессий, пулов БД)
    await bot_app.cleanup()
    logger.info("👋 Application shutdown complete")


# Привязываем наш менеджер жизненного цикла к FastAPI
fastapi_app.router.lifespan_context = lifespan

# --- ТОЧКА ВХОДА В ПРИЛОЖЕНИЕ ---

if __name__ == "__main__":
    logger.info("🏁 Launching combined web and bot application...")
    try:
        # Валидируем конфигурацию
        config.validate()

        # Запускаем Uvicorn, который будет управлять всем
        uvicorn.run(
            fastapi_app,
            host="0.0.0.0",  # Слушаем на всех интерфейсах
            port=8000,  # Порт для Cloudflare Tunnel
            log_level="info"
        )
    except Exception as e:
        logger.critical(f"💥 Fatal error during application launch: {e}\n{traceback.format_exc()}")
        sys.exit(1)
