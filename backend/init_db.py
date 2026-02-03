"""
Скрипт для инициализации базы данных на Railway
Запускается автоматически при первом старте приложения
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

async def init_database():
    """Инициализация базы данных и создание таблиц"""
    try:
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            logger.error("❌ DATABASE_URL не установлен в переменных окружения")
            return False
        
        logger.info("🔌 Подключение к базе данных...")
        logger.info(f"📍 URL: {database_url.split('@')[1] if '@' in database_url else 'скрыт'}")
        
        # Создаем engine
        engine = create_async_engine(database_url, echo=False)
        
        # Тестируем подключение
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"✅ Подключение успешно! PostgreSQL версия: {version}")
        
        # Импортируем модели
        logger.info("📦 Импорт моделей...")
        from models import Base
        
        # Создаем таблицы
        logger.info("🏗️  Создание таблиц...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ База данных инициализирована успешно!")
        
        # Проверяем созданные таблицы
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
            )
            tables = [row[0] for row in result]
            logger.info(f"📊 Созданные таблицы: {', '.join(tables)}")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def check_database_health():
    """Проверка здоровья базы данных"""
    try:
        database_url = os.getenv("DATABASE_URL")
        engine = create_async_engine(database_url, echo=False)
        
        async with engine.connect() as conn:
            # Проверяем подключение
            await conn.execute(text("SELECT 1"))
            
            # Проверяем количество записей в таблицах
            result = await conn.execute(
                text("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_total_relation_size(schemaname||'.'||tablename) as size
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                """)
            )
            
            logger.info("📊 Статус таблиц:")
            for row in result:
                schema, table, size = row
                logger.info(f"  - {table}: {size} bytes")
        
        await engine.dispose()
        logger.info("✅ База данных работает корректно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Проблема с базой данных: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Инициализация базы данных для Railway")
    logger.info("=" * 60)
    
    # Инициализация
    success = asyncio.run(init_database())
    
    if success:
        logger.info("")
        logger.info("=" * 60)
        logger.info("🏥 Проверка здоровья базы данных")
        logger.info("=" * 60)
        asyncio.run(check_database_health())
    
    logger.info("=" * 60)
    logger.info("✅ Готово!" if success else "❌ Завершено с ошибками")
    logger.info("=" * 60)
