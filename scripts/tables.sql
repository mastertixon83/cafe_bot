-- =================================================================
--         ЧАСТЬ 0: УСТАНОВКА РАСШИРЕНИЙ (если нужны)
-- =================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- =================================================================
--            ЧАСТЬ 1: СОЗДАНИЕ ВСЕХ ТАБЛИЦ БАЗЫ ДАННЫХ
-- =================================================================

-- Таблица пользователей (основа для всех остальных)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица партнёрской программы
CREATE TABLE IF NOT EXISTS referral_program (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE REFERENCES users(telegram_id) ON DELETE CASCADE,
    free_coffees INT DEFAULT 0,
    referred_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица истории приглашений
CREATE TABLE IF NOT EXISTS referral_links (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    referred_id BIGINT UNIQUE REFERENCES users(telegram_id) ON DELETE CASCADE,
    rewarded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица заказов (ключевая таблица для доски бариста)
-- ИЗМЕНЕНО: Добавлено поле payment_status.
CREATE TABLE IF NOT EXISTS orders (
    order_id      SERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    username      VARCHAR(255),
    first_name    VARCHAR(255) NOT NULL,
    payment_id    VARCHAR(255) UNIQUE,

    -- Детали заказа
    "type"        VARCHAR(255) NOT NULL,
    syrup         VARCHAR(255) DEFAULT 'Без сиропа',
    cup           VARCHAR(255) NOT NULL,
    croissant     VARCHAR(255) DEFAULT 'Без добавок',
    "time"        VARCHAR(255) NOT NULL,
    total_price   INTEGER NOT NULL,
    is_free       BOOLEAN NOT NULL DEFAULT FALSE,

    -- Поля для доски заказов
    status        VARCHAR(50) NOT NULL DEFAULT 'new',
    payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid', -- unpaid, paid, bonus

    -- Временные метки
    "timestamp"   TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица для рассылок
CREATE TABLE IF NOT EXISTS broadcast (
    id INT PRIMARY KEY DEFAULT 1,
    message_text TEXT,
    photo_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица платежей
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(255) PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    order_id INT REFERENCES orders(order_id) ON DELETE SET NULL,
    amount INTEGER NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    order_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- =================================================================
--         ЧАСТЬ 2: ФУНКЦИЯ И ТРИГГЕРЫ ДЛЯ 'updated_at'
-- =================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ language 'plpgsql';

-- Применяем триггер ко всем таблицам, где он нужен
DROP TRIGGER IF EXISTS trigger_users_updated_at ON users;
CREATE TRIGGER trigger_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_referral_program_updated_at ON referral_program;
CREATE TRIGGER trigger_referral_program_updated_at BEFORE UPDATE ON referral_program FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_orders_updated_at ON orders;
CREATE TRIGGER trigger_orders_updated_at BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_broadcast_updated_at ON broadcast;
CREATE TRIGGER trigger_broadcast_updated_at BEFORE UPDATE ON broadcast FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_payments_updated_at ON payments;
CREATE TRIGGER trigger_payments_updated_at BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- =================================================================
--         ЧАСТЬ 3: ИНДЕКСЫ ДЛЯ УСКОРЕНИЯ РАБОТЫ
-- =================================================================

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments (user_id);


-- =================================================================
--         ЧАСТЬ 4: НАЧАЛЬНЫЕ ДАННЫЕ
-- =================================================================

-- Вставляем начальную пустую запись для рассылки, если ее еще нет
INSERT INTO broadcast (id, message_text, photo_id) VALUES (1, NULL, NULL) ON CONFLICT (id) DO NOTHING;


-- =================================================================
--               ФИНАЛЬНОЕ СООБЩЕНИЕ
-- =================================================================
SELECT '>>> Все таблицы, функции и триггеры успешно созданы/обновлены. База данных готова к работе!';