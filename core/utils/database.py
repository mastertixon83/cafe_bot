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
                    dsn=config.POSTGRES_DSN,  # "postgresql://user:pass@localhost:5432/dbname"
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
        Обновить записи в таблице.
        :param table: имя таблицы
        :param data: dict с изменяемыми значениями
        :param where: SQL-условие, например "id=$1"
        :param params: список значений для условия
        """
        set_expr = ", ".join(f"{k}=${i + 1}" for i, k in enumerate(data.keys()))
        query = f"UPDATE {table} SET {set_expr} WHERE {where}"
        values = list(data.values()) + list(params)
        await self.execute(query, *values)
        logger.info(f"✏️ Updated {table}: {data}, WHERE {where} -> {params}")

    # ===== МЕТОД ДЛЯ ДОБАВЛЕНИЯ ЗАКАЗА  =====
    async def add_order(self, order_data: Dict[str, Any]) -> int:
        """
        Добавляет новый заказ в таблицу orders и возвращает его ID.
        """
        keys = ", ".join(order_data.keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(order_data)))
        query = f"INSERT INTO orders ({keys}) VALUES ({placeholders}) RETURNING order_id"
        values = list(order_data.values())

        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, *values)
            logger.info(f"✅ New order added with ID: {result}")
            return result

    # ===== МЕТОДЫ ДЛЯ АНАЛИТИКИ =====
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


# Глобальный экземпляр
postgres_client = PostgresClient()
