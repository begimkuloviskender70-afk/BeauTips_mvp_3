# ⚡ БЫСТРАЯ ИНСТРУКЦИЯ - Railway Деплой

## 🎯 Что нужно сделать (5 минут)

### 1. Регистрация на Railway
👉 https://railway.app → Sign up with GitHub

### 2. Создать PostgreSQL базу
В Railway Dashboard:
- Нажмите **"+ New"**
- Выберите **"Database" → "PostgreSQL"**
- Дождитесь создания (30 сек)

### 3. Загрузить код
```bash
# Вариант А: Через GitHub (рекомендуется)
cd railway-backend
git init
git add .
git commit -m "Initial"
git push origin main

# В Railway: "+ New" → "GitHub Repo" → Выбрать репозиторий

# Вариант Б: Через CLI
npm i -g @railway/cli
railway login
railway init
railway up
```

### 4. Настроить Environment Variables

Откройте ваш сервис → Variables → Добавьте:

```env
DATABASE_URL          postgresql+asyncpg://user:pass@host:port/db
SECRET_KEY            [32+ символа, сгенерируйте ниже]
ALGORITHM             HS256
ACCESS_TOKEN_EXPIRE_MINUTES    30
SMTP_HOST             smtp.gmail.com
SMTP_PORT             587
SMTP_USER             your-email@gmail.com
SMTP_PASSWORD         [App Password, инструкция ниже]
FROM_EMAIL            your-email@gmail.com
FROM_NAME             BeauTips
BASE_URL              https://your-app.railway.app
```

### 5. Готово! 🎉

Проверьте:
- https://your-app.railway.app/ - должен работать
- https://your-app.railway.app/api/docs - Swagger UI

---

## 🔑 Как сгенерировать SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 📧 Как получить Gmail App Password

1. Перейдите: https://myaccount.google.com/apppasswords
2. Выберите "Mail" → "Generate"
3. Скопируйте 16-символьный пароль
4. Используйте в `SMTP_PASSWORD`

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО

### DATABASE_URL формат:

❌ **Неправильно** (как дает Railway):
```
postgresql://user:pass@host:port/db
```

✅ **Правильно** (нужно изменить):
```
postgresql+asyncpg://user:pass@host:port/db
```

Добавьте `+asyncpg` после `postgresql`!

---

## 🧪 Тестирование после деплоя

```bash
python test_api.py https://your-app.railway.app
```

---

## 📚 Полная документация

- **START_HERE.md** - обзор всех файлов
- **README_RAILWAY.md** - подробная инструкция
- **DEPLOYMENT_CHECKLIST.md** - чеклист для проверки

---

## 🆘 Проблемы?

### Application failed to respond
→ Проверьте логи в Railway Dashboard
→ Убедитесь, что DATABASE_URL правильный

### CORS errors
→ Пока всё разрешено `["*"]`, работает
→ Потом ограничьте конкретными доменами

### Database connection failed
→ Формат: `postgresql+asyncpg://` (не забудьте +asyncpg)

---

## ✅ Чеклист

- [ ] PostgreSQL создан в Railway
- [ ] DATABASE_URL изменен на postgresql+asyncpg://
- [ ] SECRET_KEY сгенерирован (32+ символа)
- [ ] Gmail App Password получен
- [ ] Все переменные добавлены
- [ ] Код загружен в Railway
- [ ] Приложение запущено (статус Running)
- [ ] /api/docs открывается

---

🚀 **Всё готово! Backend работает на Railway!**

💡 При проблемах - смотрите README_RAILWAY.md (полная инструкция)
