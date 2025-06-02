"""
Celery приложение для обработки документов
"""

import os
import sys
from pathlib import Path
from celery import Celery

# Добавляем путь к shared модулям
current_dir = Path(__file__).parent
services_dir = current_dir.parent
sys.path.insert(0, str(services_dir))

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv('.env.local')

# Настройки Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Создаем Celery приложение
app = Celery(
    'admin_panel',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks']
)

# Настройки Celery для Windows
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут
    task_soft_time_limit=25 * 60,  # 25 минут
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Настройки для Windows
    worker_pool='solo',  # Используем solo pool для Windows
    worker_concurrency=1,  # Один процесс
    task_always_eager=False,  # Не выполнять задачи синхронно
    task_eager_propagates=True,
    
    # Настройки брокера
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Настройки результатов
    result_expires=3600,  # Результаты хранятся 1 час
    result_persistent=True,
    
    # Отключаем проблемные функции для Windows
    worker_disable_rate_limits=True,
    task_reject_on_worker_lost=True,
)

if __name__ == '__main__':
    app.start() 