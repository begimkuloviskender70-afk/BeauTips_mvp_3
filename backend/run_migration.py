"""
Скрипт для выполнения миграции базы данных
Добавляет поля верификации email в таблицу users
"""

import asyncio
from sqlalchemy import text
from database import engine
import os

async def run_migration():
    """Выполняет SQL миграцию для добавления полей верификации"""
    
    migration_file = os.path.join(os.path.dirname(__file__), 'migrations', 'add_email_verification.sql')
    
    if not os.path.exists(migration_file):
        print(f"❌ Файл миграции не найден: {migration_file}")
        return
    
    print("🔄 Начинаю миграцию базы данных...")
    
    try:
        async with engine.begin() as conn:
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Разделяем на отдельные SQL команды
            # Удаляем комментарии и пустые строки
            statements = []
            current_statement = []
            
            for line in sql_content.split('\n'):
                line = line.strip()
                # Пропускаем комментарии и пустые строки
                if not line or line.startswith('--'):
                    continue
                # Пропускаем блоки комментариев
                if line.startswith('--'):
                    continue
                
                current_statement.append(line)
                
                # Если строка заканчивается на ;, это конец команды
                if line.endswith(';'):
                    statement = ' '.join(current_statement)
                    if statement.strip() and not statement.strip().startswith('--'):
                        statements.append(statement)
                    current_statement = []
            
            # Выполняем каждую команду
            for i, statement in enumerate(statements, 1):
                if statement.strip():
                    try:
                        await conn.execute(text(statement))
                        print(f"✅ Команда {i}/{len(statements)} выполнена")
                    except Exception as e:
                        # Игнорируем ошибки "уже существует" для IF NOT EXISTS
                        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                            print(f"⚠️  Команда {i} пропущена (уже существует): {str(e)[:50]}")
                        else:
                            print(f"❌ Ошибка в команде {i}: {str(e)}")
                            raise
            
            await conn.commit()
        
        print("\n✅ Миграция успешно завершена!")
        print("\n📋 Добавлены поля:")
        print("   - email_verified (BOOLEAN)")
        print("   - verification_token (VARCHAR)")
        print("   - verification_token_expires (TIMESTAMP)")
        print("\n📋 Созданы индексы:")
        print("   - idx_users_verification_token")
        print("   - idx_users_email_verified")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении миграции: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Миграция базы данных: Email верификация")
    print("=" * 60)
    asyncio.run(run_migration())

