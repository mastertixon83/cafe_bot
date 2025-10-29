import asyncio
import os
from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)
from aiogram.exceptions import TelegramAPIError

# --- ВОЗЬМИТЕ ТОКЕН ИЗ ВАШЕГО .env ФАЙЛА И ВСТАВЬТЕ СЮДА ---
TOKEN = "12345:ABCDEF..."  # ЗАМЕНИТЕ НА ВАШ РЕАЛЬНЫЙ ТОКЕН БОТА


async def main():
    bot = Bot(token=TOKEN)

    print("--- НАЧИНАЕМ ПОЛНУЮ ОЧИСТКУ КОМАНД ---")

    # 1. Удаляем команды из всех возможных областей видимости
    scopes_to_clear = {
        "Default": BotCommandScopeDefault(),
        "All Private Chats": BotCommandScopeAllPrivateChats(),
        "All Group Chats": BotCommandScopeAllGroupChats(),
    }

    for name, scope in scopes_to_clear.items():
        try:
            await bot.delete_my_commands(scope=scope)
            print(f"✅ Команды для '{name}' успешно удалены.")
        except TelegramAPIError as e:
            print(f"⚠️ Не удалось удалить команды для '{name}': {e}")

    print("\n--- ОЧИСТКА ЗАВЕРШЕНА ---")
    print("--- УСТАНАВЛИВАЕМ НОВЫЕ ПРАВИЛЬНЫЕ КОМАНДЫ ---")

    # 2. Устанавливаем новые, правильные команды
    commands = [
        BotCommand(command="start", description="🏁 Перезапустить бота"),
        BotCommand(command="board", description="📋 Открыть доску заказов (для бариста)"),
        BotCommand(command="admin", description="👑 Панель администратора"),
    ]

    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        print("✅ Новые команды по умолчанию успешно установлены!")
    except TelegramAPIError as e:
        print(f"❌ Не удалось установить новые команды: {e}")

    # Закрываем сессию
    await bot.session.close()


if __name__ == "__main__":
    print("ВНИМАНИЕ: Убедитесь, что ваш основной бот (в Docker) остановлен.")
    asyncio.run(main())
