import traceback
from loguru import logger
from typing import Optional, Callable, Any
from aiogram.types import Message
from aiogram import Router


class ErrorHandler:
    """Централизованный обработчик ошибок для бота"""
    
    @staticmethod
    async def handle_llm_error(message: Message, error: Exception, context: str = "") -> None:
        """Обрабатывает ошибки LLM"""
        logger.error(f"LLM ошибка в {context}: {error}\n{traceback.format_exc()}")
        await message.answer(
            "Извините, произошла ошибка при обработке вашего запроса. Попробуйте еще раз или обратитесь к администратору."
        )
    
    @staticmethod
    async def handle_database_error(message: Message, error: Exception, context: str = "") -> None:
        """Обрабатывает ошибки базы данных"""
        logger.error(f"Ошибка базы данных в {context}: {error}\n{traceback.format_exc()}")
        await message.answer(
            "Извините, произошла ошибка при работе с базой данных. Попробуйте еще раз."
        )
    
    @staticmethod
    async def handle_general_error(message: Message, error: Exception, context: str = "") -> None:
        """Обрабатывает общие ошибки"""
        logger.error(f"Общая ошибка в {context}: {error}\n{traceback.format_exc()}")
        await message.answer(
            "Произошла непредвиденная ошибка. Попробуйте еще раз или обратитесь к администратору."
        )


def setup_error_handlers(router: Router) -> None:
    """Настраивает обработчики ошибок для роутера"""
    
    @router.errors()
    async def errors_handler(update: Any, exception: Exception) -> bool:
        """Глобальный обработчик ошибок"""
        logger.error(f"Необработанная ошибка: {exception}\n{traceback.format_exc()}")
        return True 