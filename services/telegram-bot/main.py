#!/usr/bin/env python3
"""
Главный файл Telegram бота для корпоративного RAG
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Добавляем пути к модулям
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(current_dir))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from bot.config import config
from bot.database import init_db
from bot.handlers import register_handlers

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Главная функция запуска бота"""
    
    # Проверяем конфигурацию
    if not config.validate():
        logger.error("❌ Некорректная конфигурация. Завершение работы.")
        return
    
    try:
        # Инициализируем базу данных
        logger.info("🔄 Инициализация базы данных...")
        await init_db()
        logger.info("✅ База данных инициализирована")
        
        # Создаем бота
        bot = Bot(
            token=config.TELEGRAM_BOT_TOKEN,
            parse_mode=ParseMode.HTML
        )
        
        # Создаем диспетчер
        dp = Dispatcher()
        
        # Регистрируем обработчики
        register_handlers(dp)
        
        # Проверяем подключение к боту
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен: @{bot_info.username} ({bot_info.full_name})")
        
        # Уведомляем администраторов о запуске
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    "🚀 POLIOM HR Assistant запущен и готов к работе!"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление администратору {admin_id}: {e}")
        
        # Запускаем polling
        logger.info("🔄 Запуск polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise
    finally:
        # Уведомляем администраторов об остановке
        try:
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        "⏹️ POLIOM HR Assistant остановлен."
                    )
                except:
                    pass
        except:
            pass
        
        logger.info("👋 Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1) 