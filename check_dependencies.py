#!/usr/bin/env python3
"""
Скрипт для проверки всех зависимостей перед деплоем
"""
import sys
import importlib.util

REQUIRED_PACKAGES = {
    'fastapi': 'FastAPI',
    'uvicorn': 'Uvicorn',
    'sqlalchemy': 'SQLAlchemy',
    'asyncpg': 'asyncpg',
    'jose': 'python-jose',
    'passlib': 'passlib',
    'pydantic': 'Pydantic',
    'dotenv': 'python-dotenv',
    'sklearn': 'scikit-learn',
    'numpy': 'NumPy',
    'sentence_transformers': 'sentence-transformers',
}

def check_package(package_name, display_name):
    """Проверка установки пакета"""
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        print(f"❌ {display_name} - НЕ УСТАНОВЛЕН")
        return False
    else:
        print(f"✅ {display_name} - установлен")
        return True

def main():
    print("=" * 60)
    print("🔍 Проверка зависимостей для Railway деплоя")
    print("=" * 60)
    print()
    
    all_installed = True
    
    for package, display_name in REQUIRED_PACKAGES.items():
        if not check_package(package, display_name):
            all_installed = False
    
    print()
    print("=" * 60)
    
    if all_installed:
        print("✅ Все зависимости установлены!")
        print("🚀 Проект готов к деплою на Railway")
        return 0
    else:
        print("❌ Некоторые зависимости отсутствуют")
        print("📦 Установите их командой:")
        print("   pip install -r backend/requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(main())
