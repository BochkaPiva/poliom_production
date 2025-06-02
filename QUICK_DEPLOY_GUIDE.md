# 🚀 Быстрый Guide по деплою POLIOM HR Assistant

## ✅ Что готово к деплою

**Чистый production репозиторий:** https://github.com/BochkaPiva/poliom_production.git

**Файлы в репозитории:**
- 📁 41 файл чистого production кода
- 🐳 Все Dockerfile готовы
- 🔧 docker-compose.prod.yml настроен
- 📝 Полная документация
- 🎯 Автоматический deploy.sh скрипт
- 🔒 Правильная конфигурация .env.production

## 🎯 Что нужно сделать для деплоя

### 1. Подготовка сервера (DigitalOcean)
```bash
# Создать Droplet Ubuntu 22.04 (4GB RAM минимум)
# Создать PostgreSQL кластер (managed database)
# Создать Redis кластер (managed database)
```

### 2. Подключение к серверу
```bash
ssh root@YOUR_SERVER_IP
```

### 3. Установка зависимостей на сервере
```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Установка Git
apt update && apt install -y git
```

### 4. Клонирование проекта
```bash
git clone https://github.com/BochkaPiva/poliom_production.git
cd poliom_production
```

### 5. Настройка .env.production
```bash
# Редактируем файл с вашими реальными данными:
nano .env.production

# Обязательно обновить:
- DATABASE_URL=postgresql://user:password@your-postgres-host:25060/poliom
- REDIS_URL=redis://default:password@your-redis-host:25061/0
- TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
- GIGACHAT_API_KEY=ваш_ключ_GigaChat
```

### 6. Запуск проекта
```bash
# Автоматический деплой
chmod +x deploy.sh
./deploy.sh

# ИЛИ ручной запуск
docker-compose -f docker-compose.prod.yml up -d
```

### 7. Проверка работы
```bash
# Проверить статус контейнеров
docker-compose -f docker-compose.prod.yml ps

# Проверить логи
docker-compose -f docker-compose.prod.yml logs

# Проверить бота
# Написать /start в Telegram боте

# Проверить админ-панель
# Открыть http://YOUR_SERVER_IP:8001
```

## 🔧 Команды для управления

```bash
# Перезапуск всех сервисов
docker-compose -f docker-compose.prod.yml restart

# Остановка
docker-compose -f docker-compose.prod.yml down

# Просмотр логов конкретного сервиса
docker-compose -f docker-compose.prod.yml logs telegram-bot
docker-compose -f docker-compose.prod.yml logs admin-panel

# Обновление проекта
git pull origin main
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build
```

## 📊 Мониторинг

### Проверка здоровья сервисов:
- **Telegram Bot:** http://YOUR_SERVER_IP:8080/health
- **Admin Panel:** http://YOUR_SERVER_IP:8001
- **Redis:** `docker-compose -f docker-compose.prod.yml exec redis redis-cli ping`

### Логи в реальном времени:
```bash
docker-compose -f docker-compose.prod.yml logs -f
```

## 🆘 Troubleshooting

### Если бот не отвечает:
1. Проверить токен: `env | grep TELEGRAM_BOT_TOKEN`
2. Проверить логи: `docker-compose -f docker-compose.prod.yml logs telegram-bot`
3. Проверить подключение к БД: `docker-compose -f docker-compose.prod.yml exec telegram-bot python -c "import psycopg2; print('OK')"`

### Если админ-панель не работает:
1. Проверить порт 8001: `netstat -tlnp | grep 8001`
2. Проверить логи: `docker-compose -f docker-compose.prod.yml logs admin-panel`

### Если GigaChat не работает:
1. Проверить API ключ: `env | grep GIGACHAT_API_KEY`
2. Проверить логи запросов в боте

## 💰 Стоимость на DigitalOcean

- **Droplet (4GB):** $24/месяц
- **PostgreSQL (1GB):** $15/месяц  
- **Redis (1GB):** $15/месяц
- **Итого:** ~$54/месяц

## 🎉 Готово!

После успешного деплоя у вас будет:
- ✅ Работающий Telegram бот с GigaChat
- ✅ Админ-панель для управления
- ✅ Автоматическая обработка документов
- ✅ Система мониторинга
- ✅ Готовность к production нагрузке

**Контакты для поддержки:** POLIOM Development Team 