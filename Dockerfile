FROM python:3.11-slim

# Установка рабочей директории
WORKDIR /app

# Установка системных зависимостей для PostgreSQL
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements.txt
COPY backend/requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование всего backend кода
COPY backend/ ./backend/

# Открытие порта
EXPOSE 8000

# Команда запуска
CMD cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
