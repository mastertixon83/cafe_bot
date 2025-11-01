# core/utils/database.py (ПОЛНАЯ ВЕРСИЯ С ИСПРАВЛЕНИЯМИ)

import asyncpg
from typing import Optional, Any, List, Dict, Union
from loguru import logger
from config import config


class PostgresClient:
    """
    Минимальный клиент для работы с PostgreSQL через asyncpg.
    Поддержка инициализации, закрытия пула и базовых CRUD-операций.
    """

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        logger.info("PostgresClient instance created (pool not initialized)")

    async def initialize(self) -> None:
        """Создаёт пул соединений с PostgreSQL."""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=config.POSTGRES_DSN,
                    min_size=1,
                    max_size=10,
                    command_timeout=30
                )
                logger.info("✅ PostgreSQL pool initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize PostgreSQL pool: {e}")
                raise

    async def close(self) -> None:
        """Закрывает пул соединений."""
        if self.pool:
            try:
                await self.pool.close()
                logger.info("✅ PostgreSQL pool closed successfully")
            except Exception as e:
                logger.warning(f"⚠️ Error while closing PostgreSQL pool: {e}")
            finally:
                self.pool = None

    # ===== CRUD методы =====
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Выполнить SELECT и вернуть список строк."""
        async with self.pool.acquire() as conn:
            logger.debug(f"📥 fetch: {query} {args}")
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Выполнить SELECT и вернуть одну строку или None."""
        async with self.pool.acquire() as conn:
            logger.debug(f"📥 fetchrow: {query} {args}")
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args) -> Optional[Any]:
        """Выполняет запрос и возвращает одно значение."""
        async with self.pool.acquire() as conn:
            logger.debug(f"📥 fetchval: {query} {args}")
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args) -> str:
        """Выполнить INSERT/UPDATE/DELETE и вернуть статус."""
        async with self.pool.acquire() as conn:
            logger.debug(f"⚡ execute: {query} {args}")
            return await conn.execute(query, *args)

    async def insert(self, table: str, data: Dict[str, Any]) -> None:
        """Добавить запись в таблицу."""
        keys = ", ".join(data.keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(data)))
        query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
        values = list(data.values())
        await self.execute(query, *values)
        logger.info(f"✅ Inserted into {table}: {data}")

    async def update(self, table: str, data: Dict[str, Any], where: str, params: Union[List[Any], tuple]) -> None:
        """
        Обновить записи в таблице. Автоматически нумерует плейсхолдеры.
        :param table: имя таблицы
        :param data: dict с изменяемыми значениями
        :param where: SQL-условие, например "id=$1 AND name=$2"
        :param params: список значений для условия
        """
        # Эта часть генерирует "key1=$1, key2=$2, ..."
        set_expr = ", ".join(f"{k}=${i + 1}" for i, k in enumerate(data.keys()))

        # --- НОВАЯ ЛОГИКА ---
        # Узнаем, сколько плейсхолдеров уже занято в SET
        num_set_params = len(data.keys())

        # Сдвигаем нумерацию плейсхолдеров в условии WHERE
        # Например, если было "id=$1", а в SET уже есть 2 параметра, то станет "id=$3"
        temp_where = where
        for i in range(len(params), 0, -1):
            temp_where = temp_where.replace(f'${i}', f'${i + num_set_params}')
        # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

        query = f"UPDATE {table} SET {set_expr} WHERE {temp_where}"

        # Собираем все значения в правильном порядке
        values = list(data.values()) + list(params)

        await self.execute(query, *values)
        logger.info(f"✏️ Updated {table}: {data}, WHERE {where} -> {params}")

    # <<< --- ИЗМЕНЕННЫЙ МЕТОД ЗДЕСЬ --- >>>
    async def add_order(self, order_data: Dict[str, Any]) -> Optional[asyncpg.Record]:
        """
        Добавляет новый заказ в таблицу orders и возвращает всю созданную запись.
        """
        # Добавляем статус 'new' по умолчанию, если его нет в данных
        if 'status' not in order_data:
            order_data['status'] = 'new'

        keys = ", ".join(order_data.keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(order_data)))

        # 1. Изменили 'RETURNING order_id' на 'RETURNING *'
        query = f"INSERT INTO orders ({keys}) VALUES ({placeholders}) RETURNING *"
        values = list(order_data.values())

        async with self.pool.acquire() as conn:
            # 2. Изменили 'fetchval' на 'fetchrow', чтобы получить всю строку
            new_order_record = await conn.fetchrow(query, *values)
            if new_order_record:
                # В вашей таблице колонка с id может называться 'id' или 'order_id'
                # asyncpg.Record позволяет обращаться по имени колонки
                order_id = new_order_record['id'] if 'id' in new_order_record else new_order_record.get('order_id')
                logger.info(f"✅ New order added with ID: {order_id}")
            return new_order_record

    # ===== МЕТОДЫ ДЛЯ АНАЛИТИКИ (без изменений) =====
    async def get_total_orders_count(self) -> int:
        """Получает общее количество заказов."""
        query = "SELECT COUNT(*) FROM orders;"
        return await self.fetchval(query)

    async def get_daily_orders_count(self) -> List[dict]:
        """Получает количество заказов по дням."""
        query = """
        SELECT
            DATE(created_at) AS date,
            COUNT(*) AS count
        FROM orders
        GROUP BY date
        ORDER BY date;
        """
        records = await self.fetch(query)
        return [{"date": record['date'].strftime('%Y-%m-%d'), "count": record['count']} for record in records]

    async def get_popular_drinks(self) -> List[dict]:
        """Получает топ-5 самых популярных напитков."""
        query = """
        SELECT
            type,
            COUNT(*) AS count
        FROM orders
        GROUP BY type
        ORDER BY count DESC
        LIMIT 5;
        """
        records = await self.fetch(query)
        return [{"type": record['type'], "count": record['count']} for record in records]

    async def get_free_orders_count(self) -> int:
        """Получает общее количество бесплатных заказов."""
        query = "SELECT COUNT(*) FROM orders WHERE is_free = TRUE;"
        return await self.fetchval(query)

    async def get_orders_for_export(self, period: str) -> list:
        """
        Получает список заказов из БД для экспорта в CSV.

        Args:
            period (str): Период для выборки ('today', 'week', 'month', 'all').

        Returns:
            Список записей о заказах.
        """
        query_part = ""
        if period == 'today':
            # Заказы за текущие сутки
            query_part = "WHERE created_at::date = NOW()::date"
        elif period == 'week':
            # Заказы с начала текущей недели (понедельник)
            query_part = "WHERE created_at >= date_trunc('week', NOW())"
        elif period == 'month':
            # Заказы с начала текущего месяца
            query_part = "WHERE created_at >= date_trunc('month', NOW())"

        # Для 'all' query_part остается пустым, чтобы выбрать все заказы

        query = f"SELECT * FROM orders {query_part} ORDER BY created_at DESC"
        async with self.pool.acquire() as conn:
            return await conn.fetch(query)

    async def get_orders_by_date(self, report_date: datetime.date) -> list:
        """
        Получает список заказов за конкретную дату.

        Args:
            report_date (datetime.date): Дата, за которую нужен отчет.

        Returns:
            Список записей о заказах.
        """
        query = "SELECT * FROM orders WHERE created_at::date = $1 ORDER BY created_at DESC"
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, report_date)


# Глобальный экземпляр
postgres_client = PostgresClient()
