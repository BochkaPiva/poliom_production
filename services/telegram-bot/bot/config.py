#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация для Telegram-бота POLIOM
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Config:
    """Конфигурация бота"""
    
    def __init__(self):
        # Загружаем переменные окружения
        self._load_environment()
        
        # Основные настройки
        self.TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.GIGACHAT_API_KEY: str = os.getenv("GIGACHAT_API_KEY", "")
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "")
        
        # Настройки RAG
        self.MAX_CONTEXT_LENGTH: int = int(os.getenv("MAX_CONTEXT_LENGTH", "4000"))
        self.MAX_DOCUMENTS_IN_CONTEXT: int = int(os.getenv("MAX_DOCUMENTS_IN_CONTEXT", "5"))
        self.SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
        
        # Настройки бота
        self.RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
        self.ADMIN_IDS: list = self._parse_admin_ids(os.getenv("ADMIN_IDS", ""))
        
        # Настройки логирования
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
        
        # Применяем настройки логирования
        self._setup_logging()
        
        logger.info("✅ Конфигурация загружена")
    
    def _load_environment(self):
        """Загрузка переменных окружения"""
        # Ищем .env файл в корне проекта
        project_root = Path(__file__).parent.parent.parent.parent
        env_path = project_root / '.env'
        
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"✅ Загружен .env файл: {env_path}")
        else:
            logger.warning(f"⚠️ .env файл не найден: {env_path}")
    
    def _parse_admin_ids(self, admin_ids_str: str) -> list:
        """Парсинг ID администраторов"""
        if not admin_ids_str:
            return []
        
        try:
            return [int(id_str.strip()) for id_str in admin_ids_str.split(',') if id_str.strip()]
        except ValueError as e:
            logger.error(f"❌ Ошибка парсинга ADMIN_IDS: {e}")
            return []
    
    def _setup_logging(self):
        """Настройка логирования"""
        # Устанавливаем уровень логирования
        log_level = getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)
        
        # Добавляем файловый логгер, если указан файл
        if self.LOG_FILE:
            file_handler = logging.FileHandler(self.LOG_FILE, encoding='utf-8')
            file_handler.setLevel(log_level)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)
    
    def validate(self) -> bool:
        """
        Валидация конфигурации
        
        Returns:
            bool: True если конфигурация валидна
        """
        required_vars = [
            ("TELEGRAM_BOT_TOKEN", self.TELEGRAM_BOT_TOKEN),
            ("GIGACHAT_API_KEY", self.GIGACHAT_API_KEY),
            ("DATABASE_URL", self.DATABASE_URL),
        ]
        
        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            logger.error(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
            return False
        
        logger.info("✅ Конфигурация валидна")
        return True
    
    def get_database_config(self) -> dict:
        """Получение конфигурации базы данных"""
        return {
            'url': self.DATABASE_URL,
            'echo': self.LOG_LEVEL.upper() == 'DEBUG'
        }
    
    def get_rag_config(self) -> dict:
        """Получение конфигурации RAG"""
        return {
            'max_context_length': self.MAX_CONTEXT_LENGTH,
            'max_documents': self.MAX_DOCUMENTS_IN_CONTEXT,
            'similarity_threshold': self.SIMILARITY_THRESHOLD,
            'gigachat_api_key': self.GIGACHAT_API_KEY
        }
    
    def get_bot_config(self) -> dict:
        """Получение конфигурации бота"""
        return {
            'token': self.TELEGRAM_BOT_TOKEN,
            'rate_limit': self.RATE_LIMIT_PER_MINUTE,
            'admin_ids': self.ADMIN_IDS
        }

# Создаем глобальный экземпляр конфигурации
config = Config() 