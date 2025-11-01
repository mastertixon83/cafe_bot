from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union

from config import config


class IsAdmin(BaseFilter):
    """
    Фильтр, который проверяет, является ли пользователь администратором бота.
    ID администратора берется из конфиг-файла.
    """

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        # Просто сравниваем ID пользователя, вызвавшего событие,
        # с ID админа из конфига.
        return event.from_user.id == config.ADMIN_CHAT_ID
