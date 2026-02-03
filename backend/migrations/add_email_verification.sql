-- ============================================
-- Миграция: Добавление полей верификации Email
-- Дата: 2026
-- Описание: Добавляет поля для верификации email пользователей
-- ============================================

-- Добавляем поля верификации в таблицу users
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verification_token VARCHAR(255) NULL,
ADD COLUMN IF NOT EXISTS verification_token_expires TIMESTAMP WITH TIME ZONE NULL;

-- Создаём индекс для быстрого поиска по токену
CREATE INDEX IF NOT EXISTS idx_users_verification_token 
ON users(verification_token) 
WHERE verification_token IS NOT NULL;

-- Создаём индекс для поиска неверифицированных пользователей
CREATE INDEX IF NOT EXISTS idx_users_email_verified 
ON users(email_verified) 
WHERE email_verified = FALSE;

-- Комментарии к полям
COMMENT ON COLUMN users.email_verified IS 'Флаг подтверждения email адреса';
COMMENT ON COLUMN users.verification_token IS 'Уникальный токен для верификации email (256-bit)';
COMMENT ON COLUMN users.verification_token_expires IS 'Срок действия токена верификации (24 часа)';

-- ============================================
-- Проверка миграции
-- ============================================

-- Проверяем, что поля добавлены
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default
FROM information_schema.columns
WHERE table_name = 'users' 
  AND column_name IN ('email_verified', 'verification_token', 'verification_token_expires');

-- Выводим информацию о созданных индексах
SELECT 
    indexname, 
    indexdef
FROM pg_indexes
WHERE tablename = 'users' 
  AND indexname LIKE '%verification%';

-- ============================================
-- Откат миграции (если нужно)
-- ============================================
-- DROP INDEX IF EXISTS idx_users_verification_token;
-- DROP INDEX IF EXISTS idx_users_email_verified;
-- ALTER TABLE users 
-- DROP COLUMN IF EXISTS email_verified,
-- DROP COLUMN IF EXISTS verification_token,
-- DROP COLUMN IF EXISTS verification_token_expires;

