#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный файл Telegram-бота POLIOM
Совместимость с восстановленными файлами
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем путь к shared модулям
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "shared"))

try:
    from aiogram import Bot, Dispatcher
    from aiogram.types import BotCommand
    from aiogram.fsm.storage.memory import MemoryStorage
except ImportError:
    print("❌ Ошибка: aiogram не установлен. Установите: pip install aiogram")
    sys.exit(1)

from bot.config import Config
from bot.database import init_db
from bot.handlers import router
from bot.middleware import LoggingMiddleware, AuthMiddleware, RateLimitMiddleware

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class POLIOMBot:
    def __init__(self):
        self.config = Config()
        self.bot = None
        self.dp = None
        
    async def setup_bot_commands(self):
        """Настройка команд бота"""
        commands = [
            BotCommand(command="start", description="🚀 Начать работу с ботом"),
            BotCommand(command="help", description="❓ Помощь по использованию"),
            BotCommand(command="stats", description="📊 Статистика пользователя"),
            BotCommand(command="health", description="🏥 Статус системы"),
        ]
        
        await self.bot.set_my_commands(commands)
        logger.info("✅ Команды бота настроены")
    
    def setup_middleware(self):
        """Настройка middleware"""
        # Добавляем middleware
        self.dp.message.middleware(LoggingMiddleware())
        self.dp.message.middleware(AuthMiddleware())
        self.dp.message.middleware(RateLimitMiddleware(rate_limit=10))
        
        logger.info("✅ Middleware настроены")
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        # Подключаем роутер с обработчиками
        self.dp.include_router(router)
        
        logger.info("✅ Обработчики настроены")
    
    async def startup(self):
        """Инициализация при запуске"""
        logger.info("🔄 Инициализация бота...")
        
        # Инициализируем базу данных
        try:
            await init_db()
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            raise
        
        # Настраиваем команды бота
        await self.setup_bot_commands()
        
        logger.info("🤖 POLIOM Bot готов к работе!")
    
    async def shutdown(self):
        """Завершение работы"""
        logger.info("👋 Завершение работы бота...")
        
        # Здесь можно добавить очистку ресурсов
        await self.bot.session.close()
    
    async def run(self):
        """Запуск бота"""
        # Проверяем конфигурацию
        if not self.config.validate():
            logger.error("❌ Ошибка конфигурации. Проверьте настройки.")
            return
        
        # Создаем бота и диспетчер
        self.bot = Bot(token=self.config.TELEGRAM_BOT_TOKEN)
        storage = MemoryStorage()
        self.dp = Dispatcher(storage=storage)
        
        # Настраиваем middleware и обработчики
        self.setup_middleware()
        self.setup_handlers()
        
        # Регистрируем события запуска и завершения
        self.dp.startup.register(self.startup)
        self.dp.shutdown.register(self.shutdown)
        
        # Запускаем бота
        logger.info("🚀 Запуск POLIOM Telegram Bot...")
        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=["message", "callback_query"]
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске: {e}")
            raise
        finally:
            await self.shutdown()

async def main():
    """Главная функция"""
    try:
        bot = POLIOMBot()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 