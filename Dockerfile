FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-client \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --timeout=1000 --retries=5 -r requirements.txt

COPY backend/ ./backend/
ENV PYTHONUNBUFFERED=1

CMD cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
