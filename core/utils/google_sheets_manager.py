import asyncio
import datetime
from typing import List, Dict, Any, Optional
from loguru import logger
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from oauth2client.client import AccessTokenRefreshError
import json
import time

from config import config


class GoogleSheetsManager:
    """
    Менеджер для работы с Google Sheets с переиспользованием соединений.
    """

    _instance: Optional['GoogleSheetsManager'] = None
    _initialized: bool = False

    def __new__(cls) -> 'GoogleSheetsManager':
        """Реализация Singleton паттерна."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Инициализация менеджера (выполняется только один раз)."""
        if not self._initialized:
            self.client: Optional[gspread.Client] = None
            self.credentials: Optional[ServiceAccountCredentials] = None
            self.spreadsheet: Optional[gspread.Spreadsheet] = None
            self.worksheet: Optional[gspread.Worksheet] = None

            self.service_account_file = config.GOOGLE_CREDS_FILE
            self.spreadsheet_name = config.GOOGLE_SHEETS_SPREADSHEET_NAME
            self.worksheet_name = config.GOOGLE_SHEETS_WORKSHEET_NAME

            self.max_retries = 3
            self.base_delay = 1.0
            self.max_delay = 30.0

            self.connection_stats = {
                "initialized_at": None,
                "last_used_at": None,
                "requests_count": 0,
                "errors_count": 0,
                "quota_errors_count": 0
            }

            GoogleSheetsManager._initialized = True
            logger.info("GoogleSheetsManager instance created")

    async def initialize(self) -> None:
        """
        Асинхронная инициализация Google Sheets клиента.
        """
        if self.client is not None:
            logger.info("GoogleSheetsManager already initialized")
            return

        logger.info("Initializing Google Sheets client...")

        try:
            await self._initialize_credentials()
            await self._authorize_client()
            await self._open_spreadsheet()

            self.connection_stats["initialized_at"] = datetime.datetime.now()
            self.connection_stats["requests_count"] = 0
            self.connection_stats["errors_count"] = 0

            logger.info("✅ Google Sheets client initialized successfully")
            logger.info(f"📊 Connected to spreadsheet: '{self.spreadsheet_name}', worksheet: '{self.worksheet_name}'")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Sheets client: {e}")
            await self.close()
            raise

    async def _initialize_credentials(self) -> None:
        """Инициализация учетных данных Google API."""
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]

            self.credentials = await asyncio.to_thread(
                ServiceAccountCredentials.from_json_keyfile_name,
                self.service_account_file,
                scope
            )

            logger.debug("Google API credentials loaded successfully")

        except FileNotFoundError:
            raise FileNotFoundError(
                f"Service account file '{self.service_account_file}' not found. "
                "Make sure the file exists in the project root."
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in service account file: {e}")
        except Exception as e:
            raise Exception(f"Failed to load Google API credentials: {e}")

    async def _authorize_client(self) -> None:
        """Авторизация gspread клиента."""
        try:
            self.client = await asyncio.to_thread(
                gspread.authorize,
                self.credentials
            )
            logger.debug("Google Sheets client authorized successfully")

        except AccessTokenRefreshError as e:
            raise Exception(f"Google API token refresh failed: {e}")
        except Exception as e:
            raise Exception(f"Failed to authorize Google Sheets client: {e}")

    async def _open_spreadsheet(self) -> None:
        """Открытие таблицы и рабочего листа."""
        try:
            self.spreadsheet = await asyncio.to_thread(
                self.client.open,
                self.spreadsheet_name
            )

            try:
                self.worksheet = await asyncio.to_thread(
                    self.spreadsheet.worksheet,
                    self.worksheet_name
                )
            except gspread.WorksheetNotFound:
                logger.warning(f"Worksheet '{self.worksheet_name}' not found, using first available")
                self.worksheet = self.spreadsheet.sheet1
                self.worksheet_name = self.worksheet.title

            logger.debug(f"Opened worksheet: '{self.worksheet.title}'")

        except gspread.SpreadsheetNotFound:
            raise Exception(
                f"Spreadsheet '{self.spreadsheet_name}' not found. "
                "Check the spreadsheet name and sharing permissions."
            )
        except Exception as e:
            raise Exception(f"Failed to open spreadsheet: {e}")

    async def _get_next_order_id(self) -> int:
        """
        Получает последний order_id из таблицы и возвращает следующий инкрементированный ID.
        """
        try:
            # Получаем все значения из первого столбца (где хранятся ID)
            ids = await asyncio.to_thread(self.worksheet.col_values, 1)

            # Если таблица пустая (только заголовок), начинаем с 1
            if len(ids) <= 1:
                return 1

            # Ищем последний ID, пропуская пустые строки и заголовки
            last_id = 0
            for i in reversed(ids):
                if i and i.isdigit():
                    last_id = int(i)
                    break

            return last_id + 1

        except Exception as e:
            logger.error(f"❌ Failed to get next order ID: {e}")
            return -1

    async def add_order(self, order_data: Dict[str, Any]) -> bool:
        """
        Добавляет заказ в Google Sheets с retry логикой.
        """
        if not self._is_initialized():
            logger.error("GoogleSheetsManager not initialized")
            return False

        # --- НОВЫЙ КОД ДЛЯ ИНКРЕМЕНТА ID ---
        next_order_id = await self._get_next_order_id()
        if next_order_id == -1:
            logger.error("Failed to add order due to ID generation error.")
            return False
        order_data['order_id'] = next_order_id
        # --- КОНЕЦ НОВОГО КОДА ---

        logger.info(f"Adding order to Google Sheets for user_id: {order_data.get('user_id')}")

        row_data = self._prepare_order_row(order_data)

        for attempt in range(self.max_retries):
            try:
                success = await self._add_order_with_retry(row_data, attempt)
                if success:
                    self._update_stats(success=True)
                    logger.info(f"✅ Order added successfully for user_id: {order_data.get('user_id')}")
                    return True
            except Exception as e:
                self._update_stats(success=False)
                logger.error(f"❌ Attempt {attempt + 1} failed: {e}")

                if attempt == self.max_retries - 1:
                    logger.error(f"❌ All {self.max_retries} attempts failed for order")
                    break

                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.info(f"⏳ Retrying in {delay:.1f} seconds...")
                await asyncio.sleep(delay)

        return False

    def _prepare_order_row(self, order_data: Dict[str, Any]) -> List[Any]:
        """
        Подготавливает данные заказа для записи в строку таблицы.
        """
        return [
            order_data.get('order_id'),
            order_data.get('type'),
            order_data.get('cup'),
            order_data.get('time'),
            order_data.get('is_free'),
            order_data.get('user_id'),
            order_data.get('username'),
            order_data.get('first_name'),
            order_data.get('timestamp')
        ]

    async def _add_order_with_retry(self, row_data: List[Any], attempt: int) -> bool:
        """
        Добавляет строку в таблицу с обработкой ошибок квот.
        """
        try:
            if attempt > 0:
                await self._refresh_credentials_if_needed()

            await asyncio.to_thread(self.worksheet.append_row, row_data)
            return True

        except gspread.exceptions.APIError as e:
            error_details = e.response.json() if hasattr(e, 'response') else {}
            error_code = error_details.get('error', {}).get('code')
            error_message = error_details.get('error', {}).get('message', str(e))

            if error_code == 429:
                self.connection_stats["quota_errors_count"] += 1
                logger.warning(f"⚠️ Google API quota exceeded (attempt {attempt + 1}): {error_message}")
                return False

            elif error_code in [401, 403]:
                logger.warning(f"⚠️ Authorization error (attempt {attempt + 1}): {error_message}")
                await self._refresh_credentials_if_needed()
                return False

            else:
                raise Exception(f"Google Sheets API error: {error_message}")

        except AccessTokenRefreshError:
            logger.warning(f"⚠️ Token refresh error (attempt {attempt + 1})")
            await self._refresh_credentials_if_needed()
            return False

        except Exception as e:
            raise Exception(f"Unexpected error adding order: {e}")

    async def _refresh_credentials_if_needed(self) -> None:
        """Обновляет авторизацию если необходимо."""
        try:
            logger.info("🔄 Refreshing Google Sheets authorization...")

            self.client = await asyncio.to_thread(
                gspread.authorize,
                self.credentials
            )

            self.spreadsheet = await asyncio.to_thread(
                self.client.open,
                self.spreadsheet_name
            )

            self.worksheet = await asyncio.to_thread(
                self.spreadsheet.worksheet,
                self.worksheet_name
            )

            logger.info("✅ Google Sheets authorization refreshed")

        except Exception as e:
            logger.error(f"❌ Failed to refresh Google Sheets authorization: {e}")
            raise

    def _update_stats(self, success: bool) -> None:
        """Обновляет статистику использования."""
        self.connection_stats["last_used_at"] = datetime.datetime.now()
        self.connection_stats["requests_count"] += 1

        if not success:
            self.connection_stats["errors_count"] += 1

    def _is_initialized(self) -> bool:
        """Проверяет, инициализирован ли менеджер."""
        return (self.client is not None and
                self.spreadsheet is not None and
                self.worksheet is not None)

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверяет состояние подключения к Google Sheets.
        """
        health_info = {
            "status": "unknown",
            "initialized": self._is_initialized(),
            "stats": self.connection_stats.copy()
        }

        if not self._is_initialized():
            health_info["status"] = "not_initialized"
            return health_info

        try:
            await asyncio.to_thread(self.worksheet.row_count)
            health_info["status"] = "healthy"

        except Exception as e:
            health_info["status"] = "error"
            health_info["error"] = str(e)
            logger.warning(f"Google Sheets health check failed: {e}")

        return health_info

    async def close(self) -> None:
        """
        Корректно закрывает соединение с Google Sheets.
        """
        logger.info("🧹 Closing Google Sheets connection...")

        try:
            if self.connection_stats["initialized_at"]:
                uptime = datetime.datetime.now() - self.connection_stats["initialized_at"]
                logger.info(f"📊 Google Sheets Manager Stats:")
                logger.info(f"   • Uptime: {uptime}")
                logger.info(f"   • Total requests: {self.connection_stats['requests_count']}")
                logger.info(f"   • Errors: {self.connection_stats['errors_count']}")
                logger.info(f"   • Quota errors: {self.connection_stats['quota_errors_count']}")

            self.worksheet = None
            self.spreadsheet = None
            self.client = None
            self.credentials = None

            self.connection_stats = {
                "initialized_at": None,
                "last_used_at": None,
                "requests_count": 0,
                "errors_count": 0,
                "quota_errors_count": 0
            }

            logger.info("✅ Google Sheets connection closed successfully")

        except Exception as e:
            logger.error(f"❌ Error closing Google Sheets connection: {e}")

        GoogleSheetsManager._initialized = False
        GoogleSheetsManager._instance = None


# Создаем единственный экземпляр менеджера
google_sheets_manager = GoogleSheetsManager()
