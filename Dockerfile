# Многоступенчатая сборка для уменьшения размера образа
FROM python:3.11-slim as builder

# Устанавливаем build зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем requirements
COPY backend/requirements.txt .

# Устанавливаем зависимости в отдельную директорию
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    --timeout=1000 \
    --target=/app/dependencies \
    -r requirements.txt

# Финальный образ
FROM python:3.11-slim

# Устанавливаем только runtime зависимости (без build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Копируем установленные зависимости из builder
COPY --from=builder /app/dependencies /usr/local/lib/python3.11/site-packages

# Копируем код
COPY backend/ ./backend/

# Очищаем кеши Python
RUN find /usr/local/lib/python3.11/site-packages -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -type f -name "*.pyc" -delete 2>/dev/null || true

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD cd backend && python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
