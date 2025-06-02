#!/bin/bash

# ===========================================
# RAG PROJECT DEPLOYMENT SCRIPT
# ===========================================

set -e  # Выход при любой ошибке

echo "🚀 Начинаем деплой RAG проекта..."

# Проверяем наличие необходимых файлов
if [ ! -f ".env.production" ]; then
    echo "❌ Файл .env.production не найден!"
    echo "📝 Скопируйте .env.production.example в .env.production и заполните значения"
    exit 1
fi

if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Файл docker-compose.prod.yml не найден!"
    exit 1
fi

echo "✅ Все необходимые файлы найдены"

# Загружаем переменные окружения
export $(grep -v '^#' .env.production | xargs)

echo "🔧 Конфигурация:"
echo "  - Окружение: $ENVIRONMENT"
echo "  - База данных: ${DATABASE_URL%%@*}@***"
echo "  - Redis: ${REDIS_URL%%@*}@***"
echo "  - Админ-панель порт: $ADMIN_PANEL_PORT"

# Останавливаем старые контейнеры
echo "🛑 Останавливаем старые контейнеры..."
docker-compose -f docker-compose.prod.yml --env-file .env.production down --remove-orphans

# Удаляем старые образы (опционально)
read -p "🗑️ Удалить старые Docker образы? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️ Удаляем старые образы..."
    docker system prune -f
    docker image prune -f
fi

# Собираем новые образы
echo "🔨 Собираем Docker образы..."
docker-compose -f docker-compose.prod.yml --env-file .env.production build --no-cache

# Запускаем контейнеры
echo "🚀 Запускаем контейнеры..."
docker-compose -f docker-compose.prod.yml --env-file .env.production up -d

# Ждем запуска сервисов
echo "⏳ Ждем запуска сервисов..."
sleep 30

# Проверяем статус контейнеров
echo "📊 Проверяем статус контейнеров..."
docker-compose -f docker-compose.prod.yml --env-file .env.production ps

# Проверяем health check
echo "🏥 Проверяем здоровье сервисов..."

# Проверяем админ-панель
if curl -f http://localhost:$ADMIN_PANEL_PORT/login > /dev/null 2>&1; then
    echo "✅ Админ-панель доступна на порту $ADMIN_PANEL_PORT"
else
    echo "❌ Админ-панель недоступна"
    echo "📋 Логи админ-панели:"
    docker-compose -f docker-compose.prod.yml --env-file .env.production logs admin-panel --tail=20
fi

# Проверяем Celery worker
if docker-compose -f docker-compose.prod.yml --env-file .env.production exec -T celery-worker celery -A celery_app inspect ping > /dev/null 2>&1; then
    echo "✅ Celery worker работает"
else
    echo "❌ Celery worker недоступен"
    echo "📋 Логи Celery worker:"
    docker-compose -f docker-compose.prod.yml --env-file .env.production logs celery-worker --tail=20
fi

# Показываем логи
echo "📋 Последние логи сервисов:"
echo "--- Telegram Bot ---"
docker-compose -f docker-compose.prod.yml --env-file .env.production logs telegram-bot --tail=10

echo "--- Admin Panel ---"
docker-compose -f docker-compose.prod.yml --env-file .env.production logs admin-panel --tail=10

echo "--- Celery Worker ---"
docker-compose -f docker-compose.prod.yml --env-file .env.production logs celery-worker --tail=10

echo ""
echo "🎉 Деплой завершен!"
echo ""
echo "📊 Полезные команды:"
echo "  Логи:                docker-compose -f docker-compose.prod.yml logs -f [service_name]"
echo "  Перезапуск:          docker-compose -f docker-compose.prod.yml restart [service_name]"
echo "  Остановка:           docker-compose -f docker-compose.prod.yml down"
echo "  Статус:              docker-compose -f docker-compose.prod.yml ps"
echo ""
echo "🌐 Админ-панель: http://localhost:$ADMIN_PANEL_PORT"
echo "🤖 Не забудьте настроить webhook для Telegram бота!"
echo ""
echo "✨ Удачного использования!" 