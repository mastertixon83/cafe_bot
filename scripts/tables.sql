CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,       -- ID пользователя в Telegram
    username VARCHAR(255),                    -- @username
    first_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,           -- активен ли пользователь
    created_at TIMESTAMP DEFAULT NOW(),       -- когда добавлен
    updated_at TIMESTAMP DEFAULT NOW()        -- когда обновлялся
);

-- Таблица партнёрской программы (актуальные подарки)
CREATE TABLE IF NOT EXISTS referral_program (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE REFERENCES users(telegram_id) ON DELETE CASCADE, -- кто приглашает
    free_coffees INT DEFAULT 0,        -- сколько бесплатных кофе накоплено
    referred_count INT DEFAULT 0,      -- сколько друзей привёл
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Таблица истории приглашений
CREATE TABLE IF NOT EXISTS referral_links (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,  -- кто пригласил
    referred_id BIGINT UNIQUE REFERENCES users(telegram_id) ON DELETE CASCADE,  -- кого пригласили
    rewarded BOOLEAN DEFAULT FALSE,  -- дали ли бесплатный кофе за этого друга
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица заказов
CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,            -- Уникальный инкрементный ID заказа
    type VARCHAR(255) NOT NULL,             -- Тип кофе (латте, капучино и т.д.)
    cup VARCHAR(255) NOT NULL,              -- Объём стакана
    time VARCHAR(255) NOT NULL,             -- Через сколько минут подойдёт клиент
    is_free BOOLEAN NOT NULL,               -- Флаг, был ли заказ бесплатным
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE, -- ID пользователя
    username VARCHAR(255),                  -- Юзернейм
    first_name VARCHAR(255),                -- Имя пользователя
    timestamp TIMESTAMPTZ NOT NULL,         -- Время оформления заказа
    created_at TIMESTAMPTZ DEFAULT NOW()    -- Время создания записи в БД
);

-- Чтобы updated_at обновлялся автоматически:
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Чтобы updated_at обновлялся автоматически
CREATE TRIGGER set_updated_at_referral_program
BEFORE UPDATE ON referral_program
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();