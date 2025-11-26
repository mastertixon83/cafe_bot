import traceback
from loguru import logger
from aiogram import Router, Bot
from aiogram.types import Update

from config import config


async def handle_error(update: Update, exception: Exception, bot: Bot):
    """
    Глобальный обработчик ошибок.
    Ловит все необработанные исключения из хендлеров.
    """
    # Формируем детальное сообщение об ошибке для логов и админа
    error_message = (
        f"❗️❗️❗️ Произошла необработанная ошибка!\n"
        f"Update: {update.model_dump_json(indent=2, exclude_none=True)}\n"
        f"Exception: {exception}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )
    logger.error(error_message)

    # Определяем, кому отвечать (пользователю)
    chat_id = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat.id

    # Пытаемся отправить сообщение пользователю
    if chat_id:
        try:
            await bot.send_message(
                chat_id,
                "Произошла непредвиденная ошибка. Мы уже работаем над ее устранением. Пожалуйста, попробуйте позже."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке пользователю {chat_id}: {e}")

    # Отправляем полное сообщение об ошибке администратору
    try:
        # Урезаем сообщение, если оно слишком длинное для Telegram
        if len(error_message) > 4096:
            error_message = error_message[:4000] + "...\n\n(сообщение урезано)"
        await bot.send_message(config.ADMIN_CHAT_ID, error_message)
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке администратору: {e}")


def setup_error_handlers(router: Router):
    """
    Регистрирует глобальный обработчик ошибок для роутера или диспетчера.
    """
    # F.true ловит абсолютно все ошибки
    router.errors.register(handle_error)
