from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config(BaseSettings):
    """
    Конфигурация приложения с использованием pydantic для валидации переменных окружения.
    Загружает настройки из .env файла и проверяет их наличие и корректность.
    """

    # API ключи
    TELEGRAM_BOT_TOKEN: str = Field(..., description="Токен Telegram бота")

    # Настройки бота
    BARISTA_CHAT_ID: int = Field(default=-4823870940, description="Группа Бариста")
    ADMIN_CHAT_ID: int = Field(default=8131945136, description="Группа Бариста")

    # Настройка БД
    POSTGRES_DSN: str = Field("postgresql://root:root@localhost:5432/bot_db",
                              description="Строка конекта")  # "postgresql://user:pass@localhost:5432/dbname"

    # Google Sheets
    GOOGLE_CREDS_FILE: str = str(BASE_DIR / "google_sheets_creds.json")
    GOOGLE_SHEETS_SPREADSHEET_NAME: str = "Аналитика заказов"
    GOOGLE_SHEETS_WORKSHEET_NAME: str = "Лист1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Игнорировать лишние переменные в .env
    )

    def validate(self) -> None:
        """
        Проверяет корректность конфигурации.
        Вызывается автоматически при создании экземпляра, но оставлен для совместимости
        с предыдущей версией кода.
        """
        pass  # Валидация выполняется автоматически pydantic


# Создаем экземпляр конфигурации
config = Config()
