from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Config(BaseSettings):
    """
    Конфигурация приложения с поддержкой локального и докерного запуска
    """

    # --- Общие ---
    ENV_MODE: str = Field("local", description="local / docker")
    TELEGRAM_BOT_TOKEN: str
    ADMIN_CHAT_ID: int = Field(8131945136)
    BARISTA_ID: int = Field(8131945136)
    BASE_WEBHOOK_URL: str

    # --- Postgres ---
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST_LOCAL: str
    POSTGRES_PORT_LOCAL: int
    POSTGRES_HOST_DOCKER: str
    POSTGRES_PORT_DOCKER: int

    @property
    def POSTGRES_DSN(self) -> str:
        if self.ENV_MODE == "docker":
            host = self.POSTGRES_HOST_DOCKER
            port = self.POSTGRES_PORT_DOCKER
        else:
            host = self.POSTGRES_HOST_LOCAL
            port = self.POSTGRES_PORT_LOCAL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{host}:{port}/{self.POSTGRES_DB}"

    # --- Redis ---
    REDIS_HOST_LOCAL: str
    REDIS_PORT_LOCAL: int
    REDIS_HOST_DOCKER: str
    REDIS_PORT_DOCKER: int

    @property
    def REDIS_HOST(self) -> str:
        return self.REDIS_HOST_DOCKER if self.ENV_MODE == "docker" else self.REDIS_HOST_LOCAL

    @property
    def REDIS_PORT(self) -> int:
        return self.REDIS_PORT_DOCKER if self.ENV_MODE == "docker" else self.REDIS_PORT_LOCAL

    # --- Celery ---
    CELERY_DB_NUM: int = 1

    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_DB_NUM}"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_DB_NUM}"

    # --- Google Sheets ---
    GOOGLE_CREDS_FILE: str = str(BASE_DIR / "google_sheets_creds.json")
    GOOGLE_SHEETS_SPREADSHEET_NAME: str = "Аналитика заказов"
    GOOGLE_SHEETS_WORKSHEET_NAME: str = "Лист1"
    
    # --- EPAY ---
    EPAY_CLIENT_ID: str
    EPAY_CLIENT_SECRET: str
    EPAY_TERMINAL_ID: str
    EPAY_OAUTH_URL: str
    EPAY_CREATE_INVOICE_URL: str
    EPAY_PAYMENT_PAGE_URL: str

    # --- Cloudflare ---
    CLOUDFLARE_TUNNEL_TOKEN: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def validate_env(self):
        """Простая валидация всех обязательных полей"""
        required_fields = [
            "TELEGRAM_BOT_TOKEN",
            "BASE_WEBHOOK_URL",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "EPAY_CLIENT_ID",
            "EPAY_CLIENT_SECRET",
            "EPAY_TERMINAL_ID",
            "CLOUDFLARE_TUNNEL_TOKEN"
        ]
        missing = [f for f in required_fields if not getattr(self, f)]
        if missing:
            raise RuntimeError(f"❌ Missing required config fields: {missing}")


config = Config()
