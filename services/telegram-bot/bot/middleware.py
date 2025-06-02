import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from bot.database import get_or_create_user

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования всех сообщений"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка сообщения с логированием
        
        Args:
            handler: Обработчик события
            event: Событие (сообщение)
            data: Данные контекста
            
        Returns:
            Результат обработки
        """
        user = event.from_user
        
        # Логируем входящее сообщение
        if hasattr(event, 'text') and event.text:
            logger.info(
                f"📨 Сообщение от {user.id} (@{user.username}): {event.text[:100]}..."
            )
        elif hasattr(event, 'data'):  # Callback query
            logger.info(
                f"🔘 Callback от {user.id} (@{user.username}): {event.data}"
            )
        else:
            logger.info(
                f"📎 Медиа от {user.id} (@{user.username}): {type(event).__name__}"
            )
        
        # Выполняем обработчик
        try:
            result = await handler(event, data)
            logger.debug(f"✅ Сообщение от {user.id} обработано успешно")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения от {user.id}: {e}")
            raise

class AuthMiddleware(BaseMiddleware):
    """Middleware для аутентификации и регистрации пользователей"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка сообщения с аутентификацией
        
        Args:
            handler: Обработчик события
            event: Событие (сообщение)
            data: Данные контекста
            
        Returns:
            Результат обработки
        """
        user_tg = event.from_user
        
        try:
            # Получаем или создаем пользователя в БД
            user_db = get_or_create_user(
                telegram_id=user_tg.id,
                username=user_tg.username,
                full_name=user_tg.full_name
            )
            
            # Проверяем, активен ли пользователь
            if not user_db.is_active:
                logger.warning(f"🚫 Заблокированный пользователь {user_tg.id} пытается использовать бота")
                await event.answer(
                    "❌ Ваш доступ к боту заблокирован. Обратитесь к администратору."
                )
                return
            
            # Добавляем пользователя в контекст
            data['user'] = user_db
            data['telegram_user'] = user_tg
            
            # Выполняем обработчик
            return await handler(event, data)
            
        except Exception as e:
            logger.error(f"❌ Ошибка аутентификации пользователя {user_tg.id}: {e}")
            await event.answer(
                "❌ Произошла ошибка при аутентификации. Попробуйте позже."
            )
            return

class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""
    
    def __init__(self, rate_limit: int = 5):
        """
        Инициализация middleware
        
        Args:
            rate_limit: Максимальное количество запросов в минуту
        """
        self.rate_limit = rate_limit
        self.user_requests = {}  # {user_id: [timestamp1, timestamp2, ...]}
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка сообщения с проверкой лимитов
        
        Args:
            handler: Обработчик события
            event: Событие (сообщение)
            data: Данные контекста
            
        Returns:
            Результат обработки
        """
        import time
        
        user_id = event.from_user.id
        current_time = time.time()
        
        # Инициализируем список запросов для пользователя
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        # Удаляем старые запросы (старше 1 минуты)
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if current_time - req_time < 60
        ]
        
        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.rate_limit:
            logger.warning(f"🚫 Пользователь {user_id} превысил лимит запросов")
            await event.answer(
                "⏰ Вы отправляете сообщения слишком часто. "
                "Подождите немного перед следующим запросом."
            )
            return
        
        # Добавляем текущий запрос
        self.user_requests[user_id].append(current_time)
        
        # Выполняем обработчик
        return await handler(event, data)

class AdminMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора"""
    
    def __init__(self, admin_ids: list = None):
        """
        Инициализация middleware
        
        Args:
            admin_ids: Список ID администраторов
        """
        self.admin_ids = admin_ids or []
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка сообщения с проверкой прав администратора
        
        Args:
            handler: Обработчик события
            event: Событие (сообщение)
            data: Данные контекста
            
        Returns:
            Результат обработки
        """
        user_id = event.from_user.id
        
        # Проверяем, является ли пользователь администратором
        if user_id not in self.admin_ids:
            logger.warning(f"🚫 Пользователь {user_id} пытается получить доступ к админ-функциям")
            await event.answer(
                "❌ У вас нет прав для выполнения этой команды."
            )
            return
        
        # Добавляем флаг администратора в контекст
        data['is_admin'] = True
        
        # Выполняем обработчик
        return await handler(event, data) 