-- =================================================================
--         ЧАСТЬ 0: УСТАНОВКА РАСШИРЕНИЙ (если нужны)
-- =================================================================
-- Включаем расширение для генерации UUID, т.к. оно может использоваться в будущем
-- или другими частями приложения. Безопаснее его иметь.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- =================================================================
--            ЧАСТЬ 1: СОЗДАНИЕ ВСЕХ ТАБЛИЦ БАЗЫ ДАННЫХ
-- =================================================================

-- Таблица пользователей (основа для всех остальных)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,       -- ID пользователя в Telegram
    username VARCHAR(255),                    -- @username
    first_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,           -- активен ли пользователь
    created_at TIMESTAMPTZ DEFAULT NOW(),     -- когда добавлен
    updated_at TIMESTAMPTZ DEFAULT NOW()      -- когда обновлялся
);

-- Таблица партнёрской программы (сколько бонусов у каждого пользователя)
CREATE TABLE IF NOT EXISTS referral_program (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE REFERENCES users(telegram_id) ON DELETE CASCADE, -- ссылка на пользователя
    free_coffees INT DEFAULT 0,        -- сколько бесплатных кофе накоплено
    referred_count INT DEFAULT 0,      -- сколько друзей привёл
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица истории приглашений (кто кого пригласил)
CREATE TABLE IF NOT EXISTS referral_links (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,  -- кто пригласил
    referred_id BIGINT UNIQUE REFERENCES users(telegram_id) ON DELETE CASCADE,  -- кого пригласили
    rewarded BOOLEAN DEFAULT FALSE,  -- дали ли бесплатный кофе за этого друга
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица заказов (ключевая таблица для доски бариста)
-- ВАЖНО: Добавлено поле payment_id для связи с платежом.
CREATE TABLE IF NOT EXISTS orders (
    order_id      SERIAL PRIMARY KEY,                          -- Уникальный ID заказа
    user_id       BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE, -- ID пользователя из таблицы users
    username      VARCHAR(255),                                -- Юзернейм Telegram
    first_name    VARCHAR(255) NOT NULL,                       -- Имя пользователя в Telegram
    payment_id    VARCHAR(255) UNIQUE,                         -- Ссылка на ID платежа, если заказ был оплачен

    -- Детали заказа
    "type"        VARCHAR(255) NOT NULL,                       -- Тип кофе
    syrup         VARCHAR(255) DEFAULT 'Без сиропа',           -- Выбранный сироп
    cup           VARCHAR(255) NOT NULL,                       -- Объём стакана
    croissant     VARCHAR(255) DEFAULT 'Без добавок',          -- Тип круассана
    "time"        VARCHAR(255) NOT NULL,                       -- Через сколько минут подойдёт клиент
    total_price   INTEGER NOT NULL,                            -- Итоговая стоимость заказа
    is_free       BOOLEAN NOT NULL DEFAULT FALSE,              -- Флаг, был ли заказ бесплатным

    -- Поля для доски заказов
    status        VARCHAR(50) NOT NULL DEFAULT 'new',          -- Статус заказа: new, in_progress, ready, arrived, completed, cancelled

    -- Временные метки
    "timestamp"   TIMESTAMPTZ NOT NULL,                        -- Время оформления заказа (из FSM)
    created_at    TIMESTAMPTZ DEFAULT NOW(),                   -- Время создания записи в БД (автоматически)
    updated_at    TIMESTAMPTZ DEFAULT NOW()                    -- Время последнего обновления записи (автоматически)
);

-- Таблица для рассылок
CREATE TABLE IF NOT EXISTS broadcast (
    id INT PRIMARY KEY DEFAULT 1, -- У нас всегда будет только одна запись
    message_text TEXT,            -- Текст сообщения (подпись)
    photo_id VARCHAR(255),        -- Уникальный ID файла в Telegram
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица платежей (для интеграции с Epayment)
-- ВАЖНО: payment_id теперь VARCHAR, добавлено поле order_data.
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(255) PRIMARY KEY, -- ID, который мы отправляем в Epay (число в виде строки)
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    order_id INT REFERENCES orders(order_id) ON DELETE SET NULL, -- ID созданного заказа (после успешной оплаты)
    amount INTEGER NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, paid, failed, error
    order_data JSONB, -- Здесь хранятся детали заказа до его создания
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