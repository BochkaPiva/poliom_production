"""
Асинхронный сервис для работы с RAG системой
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Добавляем путь к shared модулям
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "shared"))
sys.path.insert(0, str(project_root / "services" / "telegram-bot"))

try:
    from utils.simple_rag import SimpleRAG
    from utils.llm_client import SimpleLLMClient
    from models.document import Document, DocumentChunk
except ImportError:
    # Fallback для локальной разработки
    sys.path.insert(0, str(project_root / "services" / "shared"))
    from utils.simple_rag import SimpleRAG
    from utils.llm_client import SimpleLLMClient
    from models.document import Document, DocumentChunk

try:
    from bot.database import get_db_session
except ImportError:
    # Fallback для тестирования
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    from database import get_db_session

logger = logging.getLogger(__name__)

class RAGService:
    """
    Асинхронный сервис для работы с RAG системой
    Адаптер между синхронной RAG системой и асинхронным ботом
    """
    
    def __init__(self, gigachat_api_key: str):
        self.gigachat_api_key = gigachat_api_key
        self.rag_system = None
        self.initialized = False
    
    async def initialize(self):
        """Инициализация RAG системы"""
        if self.initialized:
            return
        
        try:
            logger.info("🔄 Инициализируем RAG систему...")
            
            # Получаем синхронную сессию БД
            db_session = next(get_db_session())
            
            # Создаем RAG систему в отдельном потоке
            loop = asyncio.get_event_loop()
            self.rag_system = await loop.run_in_executor(
                None, 
                self._create_rag_system, 
                db_session
            )
            
            self.initialized = True
            logger.info("✅ RAG система инициализирована")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации RAG системы: {e}")
            raise
    
    def _create_rag_system(self, db_session):
        """Создание RAG системы (синхронно)"""
        return SimpleRAG(db_session, self.gigachat_api_key)
    
    async def answer_question(self, question: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Асинхронный ответ на вопрос пользователя
        
        Args:
            question: Вопрос пользователя
            user_id: ID пользователя Telegram
            
        Returns:
            Dict с ответом и метаданными
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            # Выполняем поиск ответа в отдельном потоке
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.rag_system.answer_question,
                question,
                user_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения ответа: {e}")
            return {
                'answer': 'Произошла ошибка при обработке вашего вопроса.',
                'sources': [],
                'success': False,
                'error': str(e),
                'tokens_used': 0
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности RAG системы
        
        Returns:
            Dict со статусом компонентов
        """
        if not self.initialized:
            try:
                await self.initialize()
            except Exception as e:
                return {
                    'overall': False,
                    'llm': False,
                    'embeddings': False,
                    'database': False,
                    'documents_count': None,
                    'error': str(e)
                }
        
        try:
            # Проверяем статус в отдельном потоке
            loop = asyncio.get_event_loop()
            status = await loop.run_in_executor(
                None,
                self.rag_system.health_check
            )
            
            # Получаем количество документов
            documents_count = await self._get_documents_count()
            
            overall_status = all([
                status['embeddings_model'],
                status['llm_client'],
                status['database']
            ])
            
            return {
                'overall': overall_status,
                'llm': status['llm_client'],
                'embeddings': status['embeddings_model'],
                'database': status['database'],
                'documents_count': documents_count
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки статуса: {e}")
            return {
                'overall': False,
                'llm': False,
                'embeddings': False,
                'database': False,
                'documents_count': None,
                'error': str(e)
            }
    
    async def _get_documents_count(self) -> Optional[int]:
        """Получение количества документов в базе"""
        try:
            loop = asyncio.get_event_loop()
            count = await loop.run_in_executor(
                None,
                self._count_documents_sync
            )
            return count
        except Exception as e:
            logger.error(f"Ошибка подсчета документов: {e}")
            return None
    
    def _count_documents_sync(self) -> int:
        """Синхронный подсчет документов"""
        try:
            db_session = next(get_db_session())
            count = db_session.query(Document).filter(
                Document.processing_status == 'completed'
            ).count()
            return count
        except Exception as e:
            logger.error(f"Ошибка подсчета документов: {e}")
            return 0
    
    async def search_documents(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Поиск документов по запросу
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            
        Returns:
            Dict с результатами поиска
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            loop = asyncio.get_event_loop()
            chunks = await loop.run_in_executor(
                None,
                self.rag_system.search_relevant_chunks,
                query,
                limit
            )
            
            # Возвращаем чанки в правильном формате
            formatted_chunks = []
            for chunk in chunks:
                formatted_chunks.append({
                    'document_id': chunk['document_id'],
                    'content': chunk['content'],
                    'chunk_index': chunk['chunk_index'],
                    'similarity': chunk.get('similarity', 0.0)
                })
            
            return {
                'success': True,
                'chunks': formatted_chunks,
                'total_found': len(chunks)
            }
            
        except Exception as e:
            logger.error(f"Ошибка поиска документов: {e}")
            return {
                'success': False,
                'chunks': [],
                'total_found': 0,
                'error': str(e)
            }
    
    async def _get_document_info(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о документе"""
        try:
            loop = asyncio.get_event_loop()
            doc_info = await loop.run_in_executor(
                None,
                self._get_document_info_sync,
                document_id
            )
            return doc_info
        except Exception as e:
            logger.error(f"Ошибка получения информации о документе: {e}")
            return None
    
    def _get_document_info_sync(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Синхронное получение информации о документе"""
        try:
            db_session = next(get_db_session())
            document = db_session.query(Document).filter(
                Document.id == document_id
            ).first()
            
            if document:
                return {
                    'id': document.id,
                    'title': document.title,
                    'file_type': document.file_type,
                    'created_at': document.created_at
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения документа {document_id}: {e}")
            return None

    async def get_faq_by_category(self, category: str) -> Dict[str, Any]:
        """
        Получение FAQ по категории
        
        Args:
            category: Категория FAQ (payment, worktime, remote, etc.)
            
        Returns:
            Dict с вопросами и ответами
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            # Выполняем поиск FAQ в отдельном потоке
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._get_faq_by_category_sync,
                category
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения FAQ для категории {category}: {e}")
            return {
                'success': False,
                'questions': [],
                'error': str(e)
            }
    
    def _get_faq_by_category_sync(self, category: str) -> Dict[str, Any]:
        """Синхронное получение FAQ по категории"""
        try:
            if hasattr(self.rag_system, 'get_faq_by_category'):
                return self.rag_system.get_faq_by_category(category)
            else:
                # Fallback - используем поиск по ключевым словам
                category_keywords = {
                    "payment": "оплата зарплата премия",
                    "worktime": "рабочее время отпуск выходные",
                    "remote": "дистанционная работа удаленная",
                    "social": "социальная поддержка льготы",
                    "rewards": "поощрения награды бонусы",
                    "labor": "трудовые отношения договор",
                    "safety": "охрана труда безопасность"
                }
                
                keyword = category_keywords.get(category, category)
                result = self.rag_system.answer_question(f"FAQ {keyword}")
                
                if result.get('success'):
                    # Парсим ответ как FAQ
                    return {
                        'success': True,
                        'questions': [
                            {
                                'question': f"Вопросы по теме: {keyword}",
                                'answer': result['answer']
                            }
                        ]
                    }
                else:
                    return {
                        'success': False,
                        'questions': [],
                        'error': 'FAQ не найден'
                    }
                    
        except Exception as e:
            logger.error(f"Ошибка получения FAQ: {e}")
            return {
                'success': False,
                'questions': [],
                'error': str(e)
            }

    async def search_relevant_chunks(self, query: str, limit: int = 10) -> list:
        """
        Поиск релевантных чанков с информацией о документах
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            
        Returns:
            List с чанками и информацией о документах
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            loop = asyncio.get_event_loop()
            chunks = await loop.run_in_executor(
                None,
                self.rag_system.search_relevant_chunks,
                query,
                limit
            )
            
            # Обогащаем чанки информацией о документах
            enriched_chunks = []
            for chunk in chunks:
                doc_info = await self._get_document_info(chunk['document_id'])
                enriched_chunk = {
                    'document_id': chunk['document_id'],
                    'document_title': doc_info['title'] if doc_info else 'Неизвестный документ',
                    'content': chunk['content'],
                    'chunk_index': chunk['chunk_index'],
                    'similarity': chunk.get('similarity', 0.0)
                }
                enriched_chunks.append(enriched_chunk)
            
            return enriched_chunks
            
        except Exception as e:
            logger.error(f"Ошибка поиска релевантных чанков: {e}")
            return [] 