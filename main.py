from loguru import logger
import traceback
import asyncio
import signal
import sys
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from core.handlers.basic import router as basic_router
from core.handlers.admin_handlers import router as admin_router
from core.utils.database import postgres_client
from core.utils.google_sheets_manager import google_sheets_manager
from config import config


class BotApplication:
    """
    Класс для управления жизненным циклом бота с корректным graceful shutdown.
    """

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.storage = MemoryStorage()
        self.dp: Optional[Dispatcher] = None
        self.is_shutting_down = False
        self._shutdown_event = asyncio.Event()
        self._polling_task: Optional[asyncio.Task] = None
        logger.info("BotApplication instance created")

    async def initialize(self) -> None:
        """Асинхронная инициализация всех компонентов бота."""
        try:
            logger.info("Initializing bot components...")

            # Telegram Bot
            logger.info("Initializing Telegram bot...")
            self.bot = Bot(
                token=config.TELEGRAM_BOT_TOKEN,
                default=DefaultBotProperties(parse_mode="HTML")
            )
            logger.info("✅ Telegram bot initialized successfully")

            # Dispatcher
            logger.info("Initializing dispatcher...")
            self.dp = Dispatcher(storage=self.storage)
            self.dp.include_router(basic_router)
            self.dp.include_router(admin_router)
            logger.info("✅ Dispatcher initialized successfully")

            # Lifecycle hooks
            self.dp.startup.register(self._on_startup)
            self.dp.shutdown.register(self._on_shutdown)
            logger.info("✅ Lifecycle handlers registered")

            # PostgreSQL
            logger.info("Initializing PostgreSQL client...")
            await postgres_client.initialize()
            logger.info("✅ PostgreSQL client initialized successfully")

            # Google Sheets
            # logger.info("Initializing Google Sheets manager...")
            # await google_sheets_manager.initialize()
            # logger.info("✅ Google Sheets manager initialized successfully")

            logger.info("🚀 All components initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize bot components: {e}")
            await self.cleanup()
            raise

    async def _on_startup(self, bot: Bot) -> None:
        """Событие запуска бота."""
        startup_message = "🚀 Бот запущен и готов к работе!"
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, startup_message)
            logger.info("✅ Startup notification sent to admin")
        except Exception as e:
            logger.error(f"❌ Failed to send startup notification: {e}")
        logger.info(startup_message)

    async def _on_shutdown(self, bot: Bot) -> None:
        """Событие остановки бота."""
        shutdown_message = "🛑 Бот остановлен."
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, shutdown_message)
            logger.info("✅ Shutdown notification sent to admin")
        except Exception as e:
            logger.error(f"❌ Failed to send shutdown notification: {e}")
        logger.info(shutdown_message)

    def _setup_signal_handlers(self) -> None:
        """Настройка graceful shutdown по сигналам."""

        def signal_handler(signum: int, frame) -> None:
            if self.is_shutting_down:
                logger.info("Shutdown already in progress, ignoring signal")
                return
            signal_name = signal.Signals(signum).name
            logger.info(f"📡 Received {signal_name}, initiating graceful shutdown...")
            self.is_shutting_down = True
            asyncio.create_task(self._trigger_shutdown())

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("✅ Signal handlers registered (SIGTERM, SIGINT)")

    async def _trigger_shutdown(self) -> None:
        """Триггер для graceful shutdown."""
        try:
            logger.info("🔄 Triggering graceful shutdown...")
            self._shutdown_event.set()
            if self._polling_task and not self._polling_task.done():
                logger.info("Cancelling polling task...")
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    logger.info("✅ Polling task cancelled successfully")
        except Exception as e:
            logger.error(f"❌ Error during shutdown trigger: {e}")

    async def _safe_close_postgres(self) -> None:
        """Безопасное закрытие PostgreSQL пула."""
        try:
            if postgres_client and getattr(postgres_client, "pool", None):
                await postgres_client.close()
                logger.info("✅ PostgreSQL pool closed successfully")
            else:
                logger.debug("Postgres pool not initialized or already closed")
        except Exception as e:
            logger.error(f"❌ Error while closing PostgreSQL pool: {e}")

    async def _safe_close_bot_session(self) -> None:
        """Безопасное закрытие сессии бота."""
        try:
            if self.bot and self.bot.session and not self.bot.session.closed:
                await self.bot.session.close()
                logger.info("✅ Bot session closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing bot session: {e}")

    # async def _safe_close_google_sheets(self) -> None:
    #     """Безопасное закрытие Google Sheets менеджера."""
    #     try:
    #         await google_sheets_manager.close()
    #         logger.info("✅ Google Sheets manager closed successfully")
    #     except Exception as e:
    #         logger.error(f"❌ Error closing Google Sheets manager: {e}")

    async def cleanup(self) -> None:
        """Освобождение всех ресурсов."""
        logger.info("🧹 Starting cleanup process...")
        cleanup_tasks = []
        cleanup_errors = []

        # PostgreSQL
        try:
            cleanup_tasks.append(self._safe_close_postgres())
        except Exception as e:
            logger.error(f"Error preparing PostgreSQL cleanup: {e}")
            cleanup_errors.append(f"Postgres: {e}")

        # Bot session
        if self.bot and hasattr(self.bot, "session") and self.bot.session:
            logger.info("Closing bot session...")
            try:
                if not self.bot.session.closed:
                    cleanup_tasks.append(self._safe_close_bot_session())
            except Exception as e:
                logger.error(f"Error preparing bot session cleanup: {e}")
                cleanup_errors.append(f"Bot session: {e}")

        # # Google Sheets
        # try:
        #     cleanup_tasks.append(self._safe_close_google_sheets())
        # except Exception as e:
        #     logger.error(f"Error preparing Google Sheets cleanup: {e}")
        #     cleanup_errors.append(f"Google Sheets: {e}")

        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
                logger.info("✅ All cleanup tasks completed")
            except Exception as e:
                logger.error(f"❌ Error during cleanup: {e}")
                cleanup_errors.append(str(e))

        if cleanup_errors:
            logger.warning("Cleanup completed with errors:")
            for err in cleanup_errors:
                logger.warning(f"  - {err}")
        else:
            logger.info("🧹 Cleanup finished successfully")

    async def run(self) -> None:
        """Запуск бота."""
        try:
            await self.initialize()
            self._setup_signal_handlers()
            if not self.bot or not self.dp:
                raise RuntimeError("Bot or Dispatcher not initialized")

            logger.info("🚀 Starting bot polling...")
            self._polling_task = asyncio.create_task(
                self.dp.start_polling(self.bot, allowed_updates=["message", "callback_query"])
            )

            done, pending = await asyncio.wait(
                [self._polling_task, asyncio.create_task(self._shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            if self._polling_task in done:
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    logger.info("📡 Polling cancelled by shutdown signal")
                except Exception as polling_error:
                    logger.error(f"❌ Polling error: {polling_error}")
                    raise

            logger.info("✅ Bot polling stopped gracefully")
        finally:
            if not self.is_shutting_down:
                self.is_shutting_down = True
            await self.cleanup()


async def main():
    app = None
    try:
        logger.info("🚀 Starting Telegram Bot Application...")
        config.validate()
        app = BotApplication()
        await app.run()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped manually (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Critical error: {e}\n{traceback.format_exc()}")
        raise
    finally:
        if app and not app.is_shutting_down:
            logger.info("🧹 Performing final cleanup...")
            app.is_shutting_down = True
            await app.cleanup()
        logger.info("👋 Bot application terminated")


if __name__ == "__main__":
    logger.info("🏁 Launching bot application...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Application interrupted by user")
    except Exception as critical_error:
        logger.critical(f"💥 Fatal error: {critical_error}")
        sys.exit(1)
    logger.info("🔚 Application shutdown complete")
