# core/tasks.py
import asyncio
import io
import csv
import datetime
from aiogram import Bot
from aiogram.types import BufferedInputFile
from loguru import logger

from celery_app import celery_app
from config import config
from core.utils.database import PostgresClient


async def get_db_client():
    """Создаёт новый экземпляр клиента БД для текущей задачи"""
    db = PostgresClient()
    await db.initialize()
    return db


def run_async(coro):
    """Запускает асинхронную корутину в синхронном контексте Celery"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def generate_csv_string(orders: list) -> str:
    """Генерирует CSV строку из списка заказов"""
    output = io.StringIO()
    fieldnames = [
        'ID Заказа', 'Дата и время', 'Клиент', 'Username', 'Напиток', 'Сироп',
        'Объем', 'Добавка', 'Сумма', 'Статус Заказа', 'Статус Оплаты'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    for order in orders:
        row = dict(order)
        writer.writerow({
            'ID Заказа': row.get('order_id'),
            'Дата и время': row.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if row.get('created_at') else '',
            'Клиент': row.get('first_name'),
            'Username': f"@{row.get('username')}" if row.get('username') else 'N/A',
            'Напиток': row.get('type'),
            'Сироп': row.get('syrup'),
            'Объем': f"{row.get('cup')} мл",
            'Добавка': row.get('croissant'),
            'Сумма': row.get('total_price'),
            'Статус Заказа': row.get('status'),
            'Статус Оплаты': row.get('payment_status'),
        })
    return output.getvalue()


# ======================
# ЗАДАЧА РАССЫЛКИ
# ======================

@celery_app.task  # <-- ИЗМЕНЕНО: Убран явный 'name'. Celery сгенерирует его автоматически.
def broadcast_task(admin_id: int):
    async def _broadcast_wrapper():
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        db = await get_db_client()

        try:
            record = await db.fetchrow("SELECT message_text, photo_id FROM broadcast WHERE id = 1")
            if not record or (not record['message_text'] and not record['photo_id']):
                await bot.send_message(admin_id, "❌ Сообщение пустое или не найдено в БД.")
                return

            message_text = record['message_text']
            photo_id = record['photo_id']
            await bot.send_message(admin_id, "🚀 Рассылка запущена")

            users = await db.fetch("SELECT telegram_id FROM users WHERE is_active = TRUE")
            success_count, fail_count = 0, 0

            for user in users:
                try:
                    if photo_id:
                        await bot.send_photo(user['telegram_id'], photo_id, caption=message_text)
                    else:
                        await bot.send_message(user['telegram_id'], message_text)
                    success_count += 1
                except Exception:
                    fail_count += 1
                    await db.update("users", {"is_active": False}, "telegram_id = $1", [user['telegram_id']])
                await asyncio.sleep(0.05)

            report = f"🏁 Рассылка завершена!\n✅ Успешно: `{success_count}`\n❌ Ошибок: `{fail_count}`"
            await bot.send_message(admin_id, report)

        finally:
            await db.close()
            await bot.session.close()

    run_async(_broadcast_wrapper())


# ======================
# ЗАДАЧА ЭКСПОРТА ОТЧЕТОВ
# ======================

@celery_app.task  # <-- ИЗМЕНЕНО: Убран явный 'name'.
def export_orders_task(admin_id: int, period: str = None, specific_date_str: str = None):
    async def _export_wrapper():
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        db = await get_db_client()

        try:
            orders = []
            filename = "report.csv"
            caption = "📄 Ваш отчет"

            if specific_date_str:
                report_date = datetime.datetime.strptime(specific_date_str, "%Y-%m-%d").date()
                orders = await db.get_orders_by_date(report_date)
                filename = f"report_{specific_date_str}.csv"
                caption = f"📄 Отчет за {specific_date_str}"
            elif period:
                orders = await db.get_orders_for_export(period)
                filename = f"report_{period}.csv"
                caption = f"📄 Отчет за период: {period}"

            if not orders:
                await bot.send_message(admin_id, f"📂 {caption}\nЗаказов не найдено.")
                return

            csv_data = generate_csv_string(orders)
            file_to_send = BufferedInputFile(file=csv_data.encode('utf-8'), filename=filename)

            await bot.send_document(
                chat_id=admin_id,
                document=file_to_send,
                caption=f"{caption}.\nВсего строк: {len(orders)}"
            )

        finally:
            await db.close()
            await bot.session.close()

    run_async(_export_wrapper())
