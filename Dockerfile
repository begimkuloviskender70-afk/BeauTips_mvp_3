FROM python:3.11-slim

# Установка рабочей директории
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование только requirements.txt сначала (для кеширования слоя)
COPY backend/requirements.txt .

# Установка зависимостей с таймаутом и без кеша для экономии места
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --timeout=1000 -r requirements.txt

# Копирование кода приложения
COPY backend/ ./backend/

# Переменная окружения для production
ENV PYTHONUNBUFFERED=1

# Порт
EXPOSE 8000

# Команда запуска
CMD cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
