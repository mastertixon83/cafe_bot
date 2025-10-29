from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.filters import Command

from config import config  # Предполагаем, что в конфиге есть ID бариста или группы

router = Router()


# Можно сделать фильтр, чтобы команда работала только для админов/бариста
# from core.filters.is_admin import IsAdmin
# router.message.filter(IsAdmin(config.ADMIN_IDS))

@router.message(Command("board"))
async def get_board(message: Message):
    # Убедитесь, что ваш домен, проброшенный через Cloudflare, указан здесь
    web_app_url = "https://cafe_bot.n8npblocally.xyz"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="Открыть доску заказов 📋",
                web_app=WebAppInfo(url=web_app_url)
            )
        ]]
    )
    await message.answer(
        "Нажмите на кнопку ниже, чтобы открыть доску с активными заказами.",
        reply_markup=keyboard
    )
