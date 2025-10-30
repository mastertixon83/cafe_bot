import aiohttp
from loguru import logger
import uuid
from aiogram import Bot

from config import config


class EpayService:
    def __init__(self):
        self.token = None

    async def get_token(self) -> str | None:
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            "grant_type": "client_credentials",
            "scope": "webapi",
            "client_id": config.EPAY_CLIENT_ID,
            "client_secret": config.EPAY_CLIENT_SECRET,
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(config.EPAY_OAUTH_URL, data=data, headers=headers) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
                    self.token = result.get("access_token")
                    logger.info("Токен Epay успешно получен.")
                    return self.token
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка при получении токена Epay: {e}")
                return None

    async def create_invoice(self, amount: int, payment_id: uuid.UUID, description: str, bot: Bot) -> str | None:
        if not self.token:
            await self.get_token()

        if not self.token:
            logger.error("Не удалось создать счет: отсутствует токен авторизации.")
            return None

        headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
        bot_info = await bot.get_me()

        invoice_data = {
            "invoiceId": str(payment_id),
            "amount": amount,
            "currency": "KZT",
            "terminalId": config.EPAY_TERMINAL_ID,
            "description": description,
            "postLink": f"{config.BASE_WEBHOOK_URL}/webhooks/epay",
            "failurePostLink": f"{config.BASE_WEBHOOK_URL}/webhooks/epay",
            "backLink": f"https://t.me/{bot_info.username}",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(config.EPAY_CREATE_INVOICE_URL, json=invoice_data, headers=headers) as resp:
                    resp.raise_for_status()
                    logger.info(f"Счет #{payment_id} на сумму {amount} KZT успешно создан в Epay.")
                    payment_url = f"{config.EPAY_PAYMENT_PAGE_URL}?invoiceId={payment_id}"
                    return payment_url
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка при создании счета Epay #{payment_id}: {e}")
                logger.error(f"Ответ сервера: {await resp.text()}")
                return None


epay_service = EpayService()
