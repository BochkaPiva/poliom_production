#!/usr/bin/env python3
"""
Сервис для работы с LLM моделями (GigaChat)
"""

import os
import logging
import re
from typing import List, Dict, Any, Optional

# Исправляем импорты на абсолютные
try:
    from services.shared.utils.llm_client import SimpleLLMClient
    from services.shared.utils.prompts import PromptManager, PromptTemplates
except ImportError:
    # Fallback для случая, если модули не найдены
    from utils.llm_client import SimpleLLMClient
    from utils.prompts import PromptManager, PromptTemplates

logger = logging.getLogger(__name__)

class LLMService:
    """Сервис для работы с LLM - форматирование ответов поиска"""
    
    def __init__(self):
        """Инициализация сервиса"""
        # Инициализируем GigaChat клиент
        gigachat_key = os.getenv('GIGACHAT_API_KEY')
        if not gigachat_key:
            logger.warning("GIGACHAT_API_KEY не найден. LLM будет недоступен.")
            self.client = None
        else:
            self.client = SimpleLLMClient(gigachat_key)
            logger.info("LLM сервис инициализирован с GigaChat")
        
        # Инициализируем менеджер промптов
        self.prompt_manager = PromptManager()
    
    def format_search_answer(self, query: str, search_results: List[Dict[str, Any]]) -> str:
        """
        Форматирует результаты поиска в связный ответ с помощью LLM
        
        Args:
            query: Поисковый запрос пользователя
            search_results: Список результатов поиска
            
        Returns:
            str: Отформатированный ответ
        """
        if not self.client:
            return self._format_simple_answer(search_results)
        
        try:
            # Подготавливаем контекст из результатов поиска
            context_parts = []
            for i, result in enumerate(search_results[:3], 1):
                content = result.get('content', '')
                doc_name = result.get('document_name', 'Неизвестный документ')
                chunk_index = result.get('chunk_index', 0)
                similarity = result.get('similarity', 0)
                
                context_parts.append(
                    f"Фрагмент {i} (из {doc_name}, часть #{chunk_index}, релевантность: {similarity:.1%}):\n{content}"
                )
            
            context = "\n\n".join(context_parts)
            
            # Создаем улучшенный промпт
            prompt = self.prompt_manager.get_search_prompt(
                context=context,
                question=query,
                search_results=search_results
            )
            
            # Отправляем запрос к GigaChat
            response = self.client.gigachat.generate_response(
                prompt=prompt,
                max_tokens=800,
                temperature=0.2  # Низкая температура для точности
            )
            
            if response.success:
                logger.info(f"LLM успешно отформатировал ответ. Токенов: {response.tokens_used}")
                return response.text.strip()
            else:
                logger.error(f"Ошибка LLM: {response.error}")
                return self._format_simple_answer(search_results)
                
        except Exception as e:
            logger.error(f"Ошибка при форматировании ответа: {e}")
            return self._format_simple_answer(search_results)
    
    def _format_simple_answer(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Простое форматирование без LLM (fallback)
        
        Args:
            search_results: Список результатов поиска
            
        Returns:
            str: Простой отформатированный ответ
        """
        if not search_results:
            return "❌ Информация не найдена в корпоративных документах."
        
        best_result = search_results[0]
        content = best_result.get('content', '')
        doc_name = best_result.get('document_name', 'Неизвестный документ')
        chunk_index = best_result.get('chunk_index', 0)
        similarity = best_result.get('similarity', 0)
        
        # Извлекаем ключевые данные с помощью регулярных выражений
        percentages = re.findall(r'(\d+(?:,\d+)?)\s*(?:процент|%)', content, re.IGNORECASE)
        amounts = re.findall(r'(\d+(?:\s?\d{3})*(?:,\d+)?)\s*(?:рубл|₽)', content, re.IGNORECASE)
        times = re.findall(r'(\d{1,2}:\d{2}|\d{1,2}\s*час)', content, re.IGNORECASE)
        
        # Формируем ответ
        answer_parts = [f"📄 Найдена информация в документе: **{doc_name}**"]
        
        if percentages:
            answer_parts.append(f"📊 Найденные проценты: {', '.join(percentages)}%")
        
        if amounts:
            answer_parts.append(f"💰 Найденные суммы: {', '.join(amounts)} руб.")
        
        if times:
            answer_parts.append(f"⏰ Найденное время: {', '.join(times)}")
        
        # Добавляем фрагмент контента
        content_preview = content[:200] + "..." if len(content) > 200 else content
        answer_parts.append(f"\n📝 **Содержание:**\n{content_preview}")
        
        # Добавляем метаинформацию
        answer_parts.append(f"\n📚 **Источник:** {doc_name} (фрагмент #{chunk_index})")
        answer_parts.append(f"📈 **Релевантность:** {similarity:.1%}")
        
        return "\n".join(answer_parts)
    
    def summarize_document(self, document_content: str, max_length: int = 200) -> str:
        """
        Создает краткое резюме документа
        
        Args:
            document_content: Содержимое документа
            max_length: Максимальная длина резюме в словах
            
        Returns:
            str: Краткое резюме
        """
        if not self.client:
            # Простое резюме без LLM
            words = document_content.split()
            if len(words) <= max_length:
                return document_content
            return " ".join(words[:max_length]) + "..."
        
        try:
            prompt = self.prompt_manager.get_summary_prompt(
                document_content=document_content,
                max_length=max_length
            )
            
            response = self.client.gigachat.generate_response(
                prompt=prompt,
                max_tokens=400,
                temperature=0.3
            )
            
            if response.success:
                return response.text.strip()
            else:
                logger.error(f"Ошибка при создании резюме: {response.error}")
                # Fallback к простому резюме
                words = document_content.split()
                return " ".join(words[:max_length]) + "..." if len(words) > max_length else document_content
                
        except Exception as e:
            logger.error(f"Ошибка при создании резюме: {e}")
            words = document_content.split()
            return " ".join(words[:max_length]) + "..." if len(words) > max_length else document_content
    
    def handle_no_results(self, query: str) -> str:
        """
        Обрабатывает случай, когда поиск не дал результатов
        
        Args:
            query: Поисковый запрос пользователя
            
        Returns:
            str: Сообщение об отсутствии результатов
        """
        return self.prompt_manager.get_error_prompt("no_results", query)
    
    def handle_search_error(self, query: str, error: str) -> str:
        """
        Обрабатывает ошибки поиска
        
        Args:
            query: Поисковый запрос пользователя
            error: Описание ошибки
            
        Returns:
            str: Сообщение об ошибке
        """
        return self.prompt_manager.get_error_prompt("search_error", query)
    
    def suggest_clarification(self, query: str, available_topics: List[str]) -> str:
        """
        Предлагает уточнения для неясного запроса
        
        Args:
            query: Исходный запрос пользователя
            available_topics: Список доступных тем
            
        Returns:
            str: Предложения по уточнению запроса
        """
        if not self.client:
            return f"Ваш запрос '{query}' слишком общий. Попробуйте быть более конкретным."
        
        try:
            prompt = self.prompt_manager.get_clarification_prompt(query, available_topics)
            
            response = self.client.gigachat.generate_response(
                prompt=prompt,
                max_tokens=300,
                temperature=0.4
            )
            
            if response.success:
                return response.text.strip()
            else:
                return f"Ваш запрос '{query}' слишком общий. Попробуйте быть более конкретным."
                
        except Exception as e:
            logger.error(f"Ошибка при создании уточнений: {e}")
            return f"Ваш запрос '{query}' слишком общий. Попробуйте быть более конкретным."
    
    def health_check(self) -> bool:
        """
        Проверяет работоспособность LLM сервиса
        
        Returns:
            bool: True если сервис работает
        """
        if not self.client:
            return False
        
        return self.client.health_check()
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Возвращает информацию о сервисе
        
        Returns:
            Dict: Информация о состоянии сервиса
        """
        return {
            "llm_available": self.client is not None,
            "prompt_manager_active": True,
            "company_name": self.prompt_manager.company_name,
            "service_healthy": self.health_check()
        } 