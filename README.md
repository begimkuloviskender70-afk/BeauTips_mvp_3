# BeauTips Backend - Railway Deployment

🚀 Backend приложение BeauTips, готовое к деплою на Railway

## 📁 Структура проекта

```
railway-backend/
├── backend/              # Основной код приложения
│   ├── main.py          # FastAPI приложение
│   ├── database.py      # Настройки БД
│   ├── models.py        # SQLAlchemy модели
│   ├── auth.py          # Аутентификация
│   ├── schemas.py       # Pydantic схемы
│   ├── ai_service.py    # AI сервис
│   ├── email_service.py # Email сервис
│   ├── routers/         # API роутеры
│   ├── migrations/      # SQL миграции
│   ├── requirements.txt # Python зависимости
│   └── init_db.py       # Инициализация БД
├── Procfile             # Railway команда запуска
├── railway.json         # Конфигурация Railway
├── nixpacks.toml        # Настройки сборки
├── .gitignore           # Игнорируемые файлы
├── .env.example         # Пример переменных окружения
├── check_dependencies.py # Проверка зависимостей
├── README.md            # Этот файл
└── README_RAILWAY.md    # Подробная инструкция по деплою
```

## ⚡ Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone <your-repo-url>
cd railway-backend
```

### 2. Проверьте зависимости

```bash
python check_dependencies.py
```

### 3. Деплой на Railway

Следуйте подробной инструкции в **[README_RAILWAY.md](README_RAILWAY.md)**

## 🔧 Технологии

- **FastAPI** - современный веб-фреймворк
- **SQLAlchemy** - ORM для работы с БД
- **PostgreSQL** - база данных
- **asyncpg** - асинхронный драйвер PostgreSQL
- **JWT** - аутентификация
- **Google Gemini** - AI рекомендации
- **Sentence Transformers** - векторный поиск

## 📦 Основные зависимости

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.35
asyncpg==0.29.0
python-jose[cryptography]==3.3.0
google-genai>=1.0.0
sentence-transformers==3.1.1
```

Полный список в `backend/requirements.txt`

## 🌐 API Endpoints

### Аутентификация
- `POST /api/auth/register` - Регистрация
- `POST /api/auth/login` - Вход
- `POST /api/auth/verify-email` - Верификация email
- `POST /api/auth/resend-verification` - Повторная отправка верификации

### Квиз
- `POST /api/quiz/save` - Сохранение ответов
- `GET /api/quiz/{session_id}` - Получение ответов
- `POST /api/quiz/submit` - Отправка на обработку AI

### История
- `GET /api/history/sessions` - Список сессий пользователя
- `GET /api/history/recommendations/{session_id}` - Рекомендации

## 🔐 Переменные окружения

Основные переменные (см. `.env.example`):

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
SECRET_KEY=your-secret-key-32-chars-minimum
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
BASE_URL=https://your-app.railway.app
```

## 🚀 Railway Deployment

### Автоматический деплой из GitHub

1. Подключите репозиторий к Railway
2. Добавьте PostgreSQL в проект
3. Настройте переменные окружения
4. Railway автоматически развернет приложение

### Ручной деплой через CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

## 📊 Мониторинг

После деплоя доступны:

- **Swagger UI**: `https://your-app.railway.app/api/docs`
- **ReDoc**: `https://your-app.railway.app/api/redoc`
- **Health Check**: `https://your-app.railway.app/`

## 🔍 Проверка работоспособности

```bash
# Health check
curl https://your-app.railway.app/

# Тест регистрации
curl -X POST https://your-app.railway.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "password123"
  }'
```

## 🐛 Troubleshooting

### База данных не подключается
- Проверьте формат `DATABASE_URL`: должен быть `postgresql+asyncpg://`
- Убедитесь, что PostgreSQL сервис запущен

### Application failed to respond
- Проверьте логи в Railway Dashboard
- Убедитесь, что все переменные окружения установлены

### CORS ошибки
- Проверьте настройки CORS в `main.py`
- Для продакшена укажите конкретные домены

## 📖 Документация

- [Подробная инструкция по деплою](README_RAILWAY.md)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Railway Documentation](https://docs.railway.app)

## 🤝 Вклад

1. Fork проекта
2. Создайте feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменений (`git commit -m 'Add some AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## 📝 Лицензия

Этот проект создан для BeauTips

## 👥 Авторы

BeauTips Team

---

💡 **Совет**: Начните с чтения [README_RAILWAY.md](README_RAILWAY.md) для пошаговой инструкции по деплою!
