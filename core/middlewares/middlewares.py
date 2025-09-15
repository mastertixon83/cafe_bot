# middlewares.py
from aiogram.types import TelegramObject
from aiogram.dispatcher.middlewares.base import BaseMiddleware
# from core.database.database import Database
#
#
# class DbMiddleware(BaseMiddleware):
#     def __init__(self, db: Database):
#         self.db = db
#         super().__init__()
#
#     async def __call__(self, handler, event: TelegramObject, data: dict):
#         # Добавляем объект db в data
#         data['db'] = self.db
#         return await handler(event, data)
