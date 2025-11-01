# main.py

from loguru import logger
import traceback
import asyncio
import sys
from typing import Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis
from aiogram.types import BotCommand, BotCommandScopeDefault

# Импортируем роутеры
from core.handlers.basic import router as basic_router
from core.handlers.admin_handlers import router as admin_router
from core.handlers.barista_handlers import router as barista_router

# Импортируем утилиты
from core.utils.database import postgres_client
from config import config

# Импортируем наше созданное FastAPI приложение
from core.webapp import app as fastapi_app


class BotApplication:
    """
    Класс для управления жизненным циклом бота.
    """

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        logger.info("BotApplication instance created")

    async def set_bot_commands(self, bot: Bot):
        """Устанавливает команды, которые будут видны в меню Telegram."""
        commands = [
            BotCommand(command="start", description="🏁 Перезапустить бота"),
            BotCommand(command="board", description="📋 Открыть доску заказов (для бариста)"),
            BotCommand(command="admin", description="👑 Панель администратора"),
        ]
        await bot.set_my_commands(commands, BotCommandScopeDefault())
        logger.info("✅ Bot commands have been set.")

    async def initialize(self) -> None:
        """Асинхронная инициализация всех компонентов бота."""
        try:
            logger.info("Initializing bot components...")
            redis_client = Redis(host='redis_storage', port=6379, db=0)
            # redis_client = Redis(host='127.0.0.1', port=6379, db=0)
            storage = RedisStorage(
                redis=redis_client,
                state_ttl=172800,
                data_ttl=172800
            )

            self.bot = Bot(
                token=config.TELEGRAM_BOT_TOKEN,
                default=DefaultBotProperties(parse_mode="HTML")
            )
            logger.info("✅ Telegram bot initialized successfully")

            self.dp = Dispatcher(storage=storage)
            self.dp.include_router(basic_router)
            self.dp.include_router(admin_router)
            self.dp.include_router(barista_router)
            logger.info("✅ Dispatcher initialized successfully")

            self.dp.startup.register(self._on_startup)
            self.dp.shutdown.register(self._on_shutdown)
            logger.info("✅ Lifecycle handlers registered")

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
        if not self.dp: return
        logger.info("🛑 Stopping bot polling...")
        await self.dp.storage.close()
        logger.info("✅ Bot polling stopped")

    async def cleanup(self) -> None:
        """Освобождение всех ресурсов."""
        logger.info("🧹 Starting bot cleanup process...")
        try:
            if postgres_client and getattr(postgres_client, "pool", None):
                await postgres_client.close()
                logger.info("✅ PostgreSQL pool closed successfully")
        except Exception as e:
            logger.error(f"❌ Error while closing PostgreSQL pool: {e}")
        try:
            if self.bot and self.bot.session and not self.bot.session.closed:
                await self.bot.session.close()
                logger.info("✅ Bot session closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing bot session: {e}")
        logger.info("🧹 Bot cleanup finished successfully")

    async def _on_startup(self, bot: Bot) -> None:
        """Выполняется при запуске бота."""
        await self.set_bot_commands(bot)
        startup_message = "🚀 Бот запущен и готов к работе!"
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, startup_message)
            logger.info("✅ Startup notification sent to admin")
        except Exception as e:
            logger.error(f"❌ Failed to send startup notification: {e}")
        logger.info(startup_message)

    async def _on_shutdown(self, bot: Bot) -> None:
        """Выполняется при остановке бота."""
        shutdown_message = "🛑 Бот остановлен."
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, shutdown_message)
            logger.info("✅ Shutdown notification sent to admin")
        except Exception as e:
            logger.error(f"❌ Failed to send shutdown notification: {e}")
        logger.info(shutdown_message)


bot_app = BotApplication()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Контекстный менеджер FastAPI для управления жизненным циклом."""
    logger.info("🚀 Starting application lifespan...")
    await bot_app.initialize()

    # === КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ===
    # Сохраняем экземпляр бота в состоянии FastAPI.
    # Это позволит нашему эндпоинту для вебхуков получить доступ к боту
    # и отправлять сообщения пользователям после оплаты.
    app.state.bot_instance = bot_app.bot
    app.state.dp = bot_app.dp
    # === КОНЕЦ ИЗМЕНЕНИЯ ===

    polling_task = asyncio.create_task(bot_app.start_polling())
    logger.info("Bot polling has been scheduled to run in the background.")
    yield
    logger.info("🧹 Shutting down application lifespan...")
    if not polling_task.done():
        logger.info("Cancelling polling task...")
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            logger.info("✅ Polling task cancelled successfully")
    await bot_app.stop_polling()
    await bot_app.cleanup()
    logger.info("👋 Application shutdown complete")


fastapi_app.router.lifespan_context = lifespan

if __name__ == "__main__":
    logger.info("🏁 Launching combined web and bot application...")
    try:
        config.validate()
        uvicorn.run(
            fastapi_app,
            host="0.0.0.0",
            port=8010,
            log_level="info"
        )
    except Exception as e:
        logger.critical(f"💥 Fatal error during application launch: {e}\n{traceback.format_exc()}")
        sys.exit(1)
