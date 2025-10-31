import aiohttp
from loguru import logger
import uuid
from aiogram import Bot

from config import config


class EpayService:
    def __init__(self):
        self.token = None

    async def get_token(self) -> str | None:
        """
        Получает токен авторизации Epay с улучшенной обработкой ошибок и логированием.
        """
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            "grant_type": "client_credentials",
            "scope": "payment",
            "client_id": config.EPAY_CLIENT_ID,
            "client_secret": config.EPAY_CLIENT_SECRET,
        }

        logger.debug(f"Запрос токена Epay. URL: {config.EPAY_OAUTH_URL}")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(config.EPAY_OAUTH_URL, data=data, headers=headers) as resp:
                    logger.debug(f"Получен ответ от сервера токенов. Статус: {resp.status}")

                    if resp.status != 200:
                        error_body = await resp.text()
                        logger.error(f"Не удалось получить токен. Статус: {resp.status}, Тело ответа: {error_body}")
                        self.token = None
                        return None

                    result = await resp.json()
                    logger.debug(f"Тело ответа от сервера токенов: {result}")

                    access_token = result.get("access_token")
                    if not access_token:
                        logger.error(f"Токен не найден в успешном ответе от сервера: {result}")
                        self.token = None
                        return None

                    self.token = access_token
                    logger.info("Токен Epay успешно получен.")
                    return self.token

            except Exception as e:
                logger.error(f"Критическое исключение при получении токена Epay: {e}", exc_info=True)
                self.token = None
                return None

    async def create_invoice(self, amount: int, payment_id: uuid.UUID, description: str, bot: Bot,
                             is_retry: bool = False) -> str | None:
        if not self.token:
            logger.info("Токен отсутствует, запрашиваем новый.")
            await self.get_token()
            if not self.token:
                logger.error("Не удалось создать счет: первоначальное получение токена не удалось.")
                return None

        headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
        bot_info = await bot.get_me()
        invoice_data = {
            "shop_id": config.EPAY_TERMINAL_ID,
            "account_id": "01",
            "invoice_id": str(payment_id),
            "amount": amount,
            "language": "rus",
            "description": description,
            "expire_period": "1d",
            "recipient_contact": "test@example.com",
            "recipient_contact_sms": "",
            "notifier_contact_sms": "",
            "currency": "KZT",
            "post_link": f"{config.BASE_WEBHOOK_URL}/webhooks/epay",
            "failure_post_link": f"{config.BASE_WEBHOOK_URL}/webhooks/epay",
            "back_link": f"https://t.me/{bot_info.username}",
            "failure_back_link": ""
        }

        logger.debug(f"Отправка запроса на создание счета Epay. URL: {config.EPAY_CREATE_INVOICE_URL}")
        logger.debug(f"Request Body: {invoice_data}")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(config.EPAY_CREATE_INVOICE_URL, json=invoice_data, headers=headers) as resp:
                    response_text = await resp.text()

                    if resp.status == 200:
                        try:
                            result = await resp.json(content_type=None)
                            # ИЩЕМ URL В ОТВЕТЕ. Название поля гипотетическое.
                            # Вам нужно посмотреть в лог на успешный ответ.
                            payment_url = result.get("invoice_url")

                            if not payment_url:
                                logger.error(
                                    f"Счет #{payment_id} создан, но URL для оплаты не найден в ответе: {result}")
                                return None

                            logger.info(f"Счет #{payment_id} успешно создан. URL: {payment_url}")
                            return payment_url
                        except Exception as json_exc:
                            logger.error(
                                f"Не удалось распарсить JSON из успешного ответа: {json_exc}. Тело ответа: {response_text}")
                            return None

                    if "Token is not valid" in response_text and not is_retry:
                        logger.warning("Токен невалиден. Запрашиваем новый и повторяем попытку...")
                        self.token = None
                        return await self.create_invoice(amount, payment_id, description, bot, is_retry=True)

                    logger.error(f"Ошибка HTTP при создании счета Epay #{payment_id}: {resp.status}")
                    logger.error(f"Тело ответа сервера: {response_text}")
                    return None

            except Exception as e:
                logger.error(f"Непредвиденная ошибка при создании счета Epay: {e}", exc_info=True)
                return None


epay_service = EpayService()
