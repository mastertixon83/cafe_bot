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
    created_at TIMESTAMPTZ DEFAULT NOW(),       -- когда добавлен
    updated_at TIMESTAMPTZ DEFAULT NOW()        -- когда обновлялся
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
CREATE TABLE IF NOT EXISTS orders (
    order_id      SERIAL PRIMARY KEY,                          -- Уникальный ID заказа
    user_id       BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE, -- ID пользователя из таблицы users
    username      VARCHAR(255),                                -- Юзернейм Telegram
    first_name    VARCHAR(255) NOT NULL,                       -- Имя пользователя в Telegram

    -- Детали заказа
    "type"        VARCHAR(255) NOT NULL,                       -- Тип кофе
    syrup         VARCHAR(255) DEFAULT 'Без сиропа',           -- Выбранный сироп
    cup           VARCHAR(255) NOT NULL,                       -- Объём стакана
    croissant     VARCHAR(255) DEFAULT 'Без добавок',          -- Тип круассана
    "time"        VARCHAR(255) NOT NULL,                       -- Через сколько минут подойдёт клиент
    is_free       BOOLEAN NOT NULL DEFAULT FALSE,              -- Флаг, был ли заказ бесплатным

    -- Поля для доски заказов
    status        VARCHAR(50) NOT NULL DEFAULT 'new',          -- Статус заказа: new, in_progress, ready, arrived, completed, cancelled

    -- Временные метки
    "timestamp"   TIMESTAMPTZ NOT NULL,                        -- Время оформления заказа (из FSM)
    created_at    TIMESTAMPTZ DEFAULT NOW(),                   -- Время создания записи в БД (автоматически)
    updated_at    TIMESTAMPTZ DEFAULT NOW()                    -- Время последнего обновления записи (автоматически)
);


-- =================================================================
--         ЧАСТЬ 2: АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ 'updated_at'
-- =================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trigger_users_updated_at ON users;
CREATE TRIGGER trigger_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_referral_program_updated_at ON referral_program;
CREATE TRIGGER trigger_referral_program_updated_at
BEFORE UPDATE ON referral_program
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_orders_updated_at ON orders;
CREATE TRIGGER trigger_orders_updated_at
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();


-- =================================================================
--         ЧАСТЬ 3: ИНДЕКСЫ ДЛЯ УСКОРЕНИЯ РАБОТЫ
-- =================================================================

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at);
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id);


-- =================================================================
--         ЧАСТЬ 4: ТАБЛИЦА ДЛЯ РАССЫЛОК (ОБНОВЛЕНО)
-- =================================================================

-- Удаляем старую таблицу, если она есть
DROP TABLE IF EXISTS broadcast;

-- Создаем новую с полем photo_id
CREATE TABLE IF NOT EXISTS broadcast (
    id INT PRIMARY KEY DEFAULT 1, -- У нас всегда будет только одна запись
    message_text TEXT,            -- Текст сообщения (подпись)
    photo_id VARCHAR(255),        -- Уникальный ID файла в Telegram
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Добавляем триггер для автоматического обновления updated_at
DROP TRIGGER IF EXISTS trigger_broadcast_updated_at ON broadcast;
CREATE TRIGGER trigger_broadcast_updated_at
BEFORE UPDATE ON broadcast
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Вставляем начальную пустую запись, если ее еще нет
INSERT INTO broadcast (id, message_text, photo_id) VALUES (1, NULL, NULL) ON CONFLICT (id) DO NOTHING;


-- =================================================================
--               ФИНАЛЬНОЕ СООБЩЕНИЕ
-- =================================================================
SELECT '>>> Все таблицы, функции и триггеры успешно созданы/обновлены. База данных готова к работе!';