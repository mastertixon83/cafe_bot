# core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # <- Изменено для корректного пути к creds.json


class Config(BaseSettings):
    """
    Конфигурация приложения с использованием pydantic для валидации переменных окружения.
    Загружает настройки из .env файла и проверяет их наличие и корректность.
    """

    # API ключи
    TELEGRAM_BOT_TOKEN: str = Field(..., description="Токен Telegram бота")

    # Настройки бота
    ADMIN_CHAT_ID: int = Field(default=8131945136, description="Администратор")
    BARISTA_ID: int = Field(default=8131945136, description="Бариста")

    # Настройка БД
    POSTGRES_DSN: str = Field("postgresql://root:root@db:5432/bot_db",
                              description="Строка конекта")

    # Google Sheets
    GOOGLE_CREDS_FILE: str = str(BASE_DIR / "google_sheets_creds.json")
    GOOGLE_SHEETS_SPREADSHEET_NAME: str = "Аналитика заказов"
    GOOGLE_SHEETS_WORKSHEET_NAME: str = "Лист1"

    # --- НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ EPAY ---
    BASE_WEBHOOK_URL: str
    EPAY_CLIENT_ID: str
    EPAY_CLIENT_SECRET: str
    EPAY_TERMINAL_ID: str
    EPAY_OAUTH_URL: str = "https://test-epay-oauth.epayment.kz/oauth2/token"
    EPAY_CREATE_INVOICE_URL: str = "https://test-epay-api.epayment.kz/invoice"
    EPAY_PAYMENT_PAGE_URL: str = "https://test-epay.homebank.kz/epay2/personal/start.html"
    # --- КОНЕЦ НОВЫХ ПЕРЕМЕННЫХ ---

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def validate(self) -> None:
        pass


config = Config()
