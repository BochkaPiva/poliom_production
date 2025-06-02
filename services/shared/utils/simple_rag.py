# services/shared/utils/simple_rag.py

import logging
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from sqlalchemy import text

# Исправляем импорт на абсолютный
try:
    from services.shared.models.document import Document, DocumentChunk
except ImportError:
    # Fallback для случая, если модуль не найден
    from models.document import Document, DocumentChunk

from .llm_client import SimpleLLMClient, LLMResponse

logger = logging.getLogger(__name__)

class SimpleRAG:
    """
    Максимально простая RAG система
    - Локальные эмбеддинги (бесплатно)
    - GigaChat для ответов (бесплатно)
    - Никаких сложностей!
    """
    
    def __init__(self, db_session: Session, gigachat_api_key: str):
        """
        Инициализация RAG системы
        
        Args:
            db_session: Сессия базы данных
            gigachat_api_key: API ключ для GigaChat
        """
        self.db_session = db_session
        self.llm_client = SimpleLLMClient(gigachat_api_key)
        self.similarity_threshold = 0.5  # Порог схожести для векторного поиска
        
        # Инициализируем логгер
        self.logger = logging.getLogger(__name__)
        
        # Загружаем модель эмбеддингов
        self.logger.info("Загружаем модель эмбеддингов...")
        self.embedding_model = SentenceTransformer('cointegrated/rubert-tiny2')
        self.logger.info("Модель эмбеддингов загружена!")
        
    def create_embedding(self, text: str) -> List[float]:
        """Создание эмбеддинга для текста"""
        try:
            embedding = self.embedding_model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            self.logger.error(f"Ошибка создания эмбеддинга: {e}")
            return []
    
    def search_relevant_chunks(self, question: str, limit: int = 15) -> List[Dict]:
        """
        Поиск релевантных чанков для ответа на вопрос
        
        Args:
            question: Вопрос пользователя
            limit: Максимальное количество чанков для возврата
            
        Returns:
            List[Dict]: Список релевантных чанков с метаданными
        """
        try:
            # 1. Создаем эмбеддинг для вопроса
            question_embedding = self.create_embedding(question)
            self.logger.info(f"Создан эмбеддинг для вопроса, размерность: {len(question_embedding)}")
            
            # 2. Выполняем векторный поиск с высоким порогом качества
            self.logger.info("Пытаемся выполнить векторный поиск...")
            
            # Используем pgvector для поиска похожих эмбеддингов
            query = text("""
                SELECT dc.id, dc.document_id, dc.chunk_index, dc.content,
                       1 - (dc.embedding <=> :embedding) as similarity,
                       dc.content_length
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.processing_status = 'completed'
                  AND dc.embedding IS NOT NULL
                  AND dc.content_length > 200
                  AND dc.content_length < 3000
                  AND dc.content NOT ILIKE '%приложение%'
                  AND dc.content NOT ILIKE '%утверждаю%'
                  AND dc.content NOT ILIKE '%генеральный директор%'
                  AND dc.content NOT ILIKE '%система менеджмента%'
                  AND dc.content NOT ILIKE '%положение%о%'
                  AND dc.content NOT ILIKE '%введено впервые%'
                  AND dc.content NOT ILIKE '%дата введения%'
                ORDER BY dc.embedding <=> :embedding
                LIMIT :limit
            """)
            
            result = self.db_session.execute(query, {
                'embedding': str(question_embedding),
                'limit': limit * 2
            })
            
            vector_chunks = []
            for row in result:
                # Повышаем порог схожести и добавляем проверку качества контента
                if (row.similarity > 0.65 and 
                    self._is_relevant_content(row.content, question)):
                    vector_chunks.append({
                        'id': row.id,
                        'document_id': row.document_id,
                        'chunk_index': row.chunk_index,
                        'content': row.content,
                        'similarity': row.similarity,
                        'search_type': 'vector',
                        'content_length': row.content_length
                    })
            
            self.logger.info(f"Векторный поиск завершен, найдено {len(vector_chunks)} качественных чанков")
            
            # 3. Дополняем улучшенным текстовым поиском
            text_chunks = []
            
            if len(vector_chunks) < limit:
                keywords = self._extract_keywords(question)
                
                if keywords:
                    self.logger.info(f"Выполняем текстовый поиск по ключевым словам: {keywords}")
                    
                    # Улучшенный запрос для текстового поиска
                    conditions = []
                    params = {}
                    
                    for i, keyword in enumerate(keywords[:5]):  # Ограничиваем количество ключевых слов
                        param_name = f'keyword_{i}'
                        conditions.append(f"dc.content ILIKE :{param_name}")
                        params[param_name] = f'%{keyword}%'
                    
                    text_query = text(f"""
                        SELECT dc.id, dc.document_id, dc.chunk_index, dc.content,
                                0.6 as similarity, dc.content_length
                        FROM document_chunks dc
                        JOIN documents d ON dc.document_id = d.id
                        WHERE d.processing_status = 'completed'
                          AND dc.content_length > 200
                          AND dc.content_length < 3000
                          AND dc.content NOT ILIKE '%приложение%'
                          AND dc.content NOT ILIKE '%утверждаю%'
                          AND dc.content NOT ILIKE '%генеральный директор%'
                          AND dc.content NOT ILIKE '%система менеджмента%'
                          AND dc.content NOT ILIKE '%положение%о%'
                          AND dc.content NOT ILIKE '%введено впервые%'
                          AND dc.content NOT ILIKE '%дата введения%'
                          AND ({' OR '.join(conditions)})
                        ORDER BY dc.content_length DESC
                        LIMIT :limit
                    """)
                    
                    params['limit'] = limit
                    text_result = self.db_session.execute(text_query, params)
                    
                    for row in text_result:
                        # Проверяем, что этот чанк еще не найден и содержит релевантную информацию
                        if (not any(chunk['id'] == row.id for chunk in vector_chunks) and
                            self._is_relevant_content(row.content, question)):
                            
                            # Дополнительная проверка на пересечение ключевых слов
                            content_words = set(row.content.lower().split())
                            question_words = set(question.lower().split())
                            overlap = len(content_words & question_words)
                            
                            if overlap >= 2:  # Минимум 2 общих слова
                                text_chunks.append({
                                    'id': row.id,
                                    'document_id': row.document_id,
                                    'chunk_index': row.chunk_index,
                                    'content': row.content,
                                    'similarity': 0.6 + (overlap * 0.05),  # Бонус за больше совпадений
                                    'search_type': 'text',
                                    'content_length': row.content_length
                                })
                    
                    self.logger.info(f"Текстовый поиск завершен, найдено {len(text_chunks)} дополнительных чанков")
            
            # 4. Объединяем результаты и сортируем по релевантности
            all_chunks = vector_chunks + text_chunks
            
            # Сортируем по схожести (убывание)
            all_chunks.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Ограничиваем количество результатов
            final_chunks = all_chunks[:limit]
            
            if not final_chunks:
                self.logger.info("Улучшенный поиск не дал результатов, используем fallback")
                return self._fallback_search(question, limit)
            
            return final_chunks
            
        except Exception as e:
            self.logger.error(f"Ошибка в search_relevant_chunks: {str(e)}")
            return self._fallback_search(question, limit)
    
    def _extract_keywords(self, question: str) -> List[str]:
        """Извлечение ключевых слов из вопроса"""
        # Расширенный словарь синонимов для лучшего поиска
        synonyms = {
            'аванс': ['аванс', 'авансовая', 'авансовый', 'первая часть', 'первая половина', 'предоплата'],
            'зарплата': ['зарплата', 'заработная плата', 'оплата труда', 'вознаграждение', 'зп'],
            'выплата': ['выплата', 'выплачивается', 'перечисление', 'начисление', 'выдача'],
            'дата': ['дата', 'число', 'срок', 'время', 'когда', 'день'],
            'размер': ['размер', 'сумма', 'процент', 'сколько', 'величина'],
            'отпуск': ['отпуск', 'отпускные', 'отдых', 'каникулы'],
            'больничный': ['больничный', 'болезнь', 'нетрудоспособность', 'лист нетрудоспособности'],
            'премия': ['премия', 'бонус', 'поощрение', 'надбавка'],
            'договор': ['договор', 'контракт', 'соглашение', 'трудовой договор'],
            'увольнение': ['увольнение', 'расторжение', 'прекращение', 'уход'],
            'график': ['график', 'расписание', 'режим', 'время работы'],
            'документы': ['документы', 'справки', 'бумаги', 'формы']
        }
        
        question_lower = question.lower()
        keywords = set()
        
        # Ищем прямые совпадения с синонимами
        for base_word, word_list in synonyms.items():
            for word in word_list:
                if word in question_lower:
                    keywords.update([base_word])  # Добавляем базовое слово
                    keywords.add(word)  # И само найденное слово
                    break
        
        # Добавляем числа (даты, проценты)
        import re
        numbers = re.findall(r'\b\d{1,2}\b', question)
        for num in numbers:
            keywords.add(num)
        
        # Добавляем важные слова длиннее 3 символов
        words = re.findall(r'\b[а-яё]{4,}\b', question_lower)
        stop_words = {'когда', 'какой', 'какая', 'какие', 'сколько', 'почему', 'зачем', 'откуда', 'куда'}
        for word in words:
            if word not in stop_words:
                keywords.add(word)
        
        return list(keywords)[:10]  # Ограничиваем количество ключевых слов
    
    def _fallback_search(self, question: str, limit: int) -> List[Dict]:
        """Резервный поиск при отсутствии результатов"""
        try:
            self.logger.info("Используем текстовый поиск как fallback")
            
            # Простой текстовый поиск по содержимому
            query = text("""
                SELECT dc.id, dc.document_id, dc.chunk_index, dc.content,
                       0.5 as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.processing_status = 'completed'
                  AND (dc.content ILIKE :search_term1 
                       OR dc.content ILIKE :search_term2
                       OR dc.content ILIKE :search_term3)
                LIMIT :limit
            """)
            
            # Извлекаем основные слова из вопроса
            words = question.lower().split()
            search_terms = [f'%{word}%' for word in words if len(word) > 2][:3]
            
            if not search_terms:
                return []
            
            params = {
                'search_term1': search_terms[0] if len(search_terms) > 0 else '%',
                'search_term2': search_terms[1] if len(search_terms) > 1 else search_terms[0],
                'search_term3': search_terms[2] if len(search_terms) > 2 else search_terms[0],
                'limit': limit
            }
            
            result = self.db_session.execute(query, params)
            
            chunks = []
            for row in result:
                chunks.append({
                    'id': row.id,
                    'document_id': row.document_id,
                    'chunk_index': row.chunk_index,
                    'content': row.content,
                    'similarity': row.similarity,
                    'search_type': 'fallback'
                })
            
            self.logger.info(f"Текстовый поиск завершен, найдено {len(chunks)} чанков")
            return chunks
            
        except Exception as e:
            self.logger.error(f"Ошибка в fallback поиске: {str(e)}")
            return []
    
    def format_context(self, chunks: List[DocumentChunk]) -> str:
        """Форматирование контекста из найденных чанков"""
        if not chunks:
            return "Информация не найдена."
        
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            # Получаем название документа
            document = self.db_session.query(Document).filter(
                Document.id == chunk['document_id']
            ).first()
            
            doc_title = document.title if document else "Неизвестный документ"
            
            context_parts.append(
                f"[Источник {i}: {doc_title}]\n{chunk['content']}\n"
            )
        
        return "\n".join(context_parts)
    
    def answer_question(self, 
                       question: str,
                       user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Главная функция - ответ на вопрос пользователя
        
        Args:
            question: Вопрос пользователя
            user_id: ID пользователя (для логирования)
            
        Returns:
            Dict с ответом и метаданными
        """
        try:
            self.logger.info(f"Обрабатываем вопрос: {question[:100]}...")
            
            # 1. Ищем релевантные документы
            relevant_chunks = self.search_relevant_chunks(question, limit=20)  # Увеличиваем лимит
            
            if not relevant_chunks:
                return {
                    'answer': 'К сожалению, я не нашел информации по вашему вопросу в корпоративной базе знаний. Попробуйте переформулировать вопрос или обратитесь к HR-отделу.',
                    'sources': [],
                    'chunks': [],
                    'files': [],
                    'success': True,
                    'tokens_used': 0
                }
            
            # 2. Улучшенное формирование контекста - берем лучшие чанки
            top_chunks = relevant_chunks[:10]  # Ограничиваем до 10 лучших чанков
            context = self.format_context(top_chunks)
            
            # ОТЛАДКА: Выводим контекст в лог
            self.logger.info(f"🔍 КОНТЕКСТ ДЛЯ LLM (длина: {len(context)} символов):")
            self.logger.info("="*80)
            self.logger.info(context[:2000] + "..." if len(context) > 2000 else context)
            self.logger.info("="*80)
            
            # 3. Получаем ответ от LLM с улучшенным промптом
            enhanced_prompt = f"""
Вопрос: {question}

Контекст: {context}

Требования к ответу:
1. Будь максимально точным и подробным
2. Используй только информацию из предоставленного контекста
3. Структурируй ответ с нумерованными списками где это уместно
4. Если в контексте есть конкретные цифры, даты, суммы - обязательно укажи их
5. Отвечай на русском языке
"""
            
            llm_response = self.llm_client.generate_answer(
                context=enhanced_prompt,
                question=question
            )
            
            if not llm_response.success:
                return {
                    'answer': 'Извините, произошла ошибка при генерации ответа. Попробуйте позже.',
                    'sources': [],
                    'chunks': [],
                    'files': [],
                    'success': False,
                    'error': llm_response.error,
                    'tokens_used': 0
                }
            
            # 4. Формируем источники и файлы с дедупликацией
            sources = []
            files = []
            seen_documents = set()
            
            for chunk in top_chunks:
                document = self.db_session.query(Document).filter(
                    Document.id == chunk['document_id']
                ).first()
                
                if document and document.title not in seen_documents:
                    sources.append({
                        'title': document.title,
                        'chunk_index': chunk['chunk_index'],
                        'document_id': document.id
                    })
                    
                    # Добавляем полную информацию о файле для прикрепления
                    files.append({
                        'title': document.title,
                        'file_path': document.file_path,  # Полный путь к файлу
                        'document_id': document.id,
                        'similarity': chunk['similarity'],
                        'file_size': document.file_size,
                        'file_type': document.file_type,
                        'original_filename': document.original_filename
                    })
                    
                    seen_documents.add(document.title)
            
            # 5. Постобработка ответа для улучшения форматирования
            formatted_answer = self._post_process_answer(llm_response.text)

            # 6. Логируем запрос (опционально)
            if user_id:
                self._log_query(user_id, question, formatted_answer, len(relevant_chunks))
            
            return {
                'answer': formatted_answer,
                'sources': sources,
                'chunks': relevant_chunks,
                'files': files[:5],  # Ограничиваем до 5 файлов
                'success': True,
                'tokens_used': llm_response.tokens_used,
                'chunks_found': len(relevant_chunks),
                'context_length': len(context)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка в answer_question: {str(e)}")
            return {
                'answer': 'Произошла техническая ошибка. Обратитесь к администратору.',
                'sources': [],
                'chunks': [],
                'files': [],
                'success': False,
                'error': str(e),
                'tokens_used': 0
            }
    
    def _post_process_answer(self, answer: str) -> str:
        """
        Постобработка ответа для правильного форматирования
        
        Args:
            answer: Исходный ответ от LLM
            
        Returns:
            str: Обработанный ответ
        """
        # Убираем лишние пробелы и переносы
        answer = answer.strip()
        
        # Нормализуем переносы строк - убираем одиночные переносы, оставляем двойные
        lines = answer.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # Добавляем только непустые строки
                cleaned_lines.append(line)
        
        # Объединяем строки с одним переносом между ними
        result = '\n'.join(cleaned_lines)
        
        # Убираем возможные дублирующиеся фразы
        sentences = result.split('. ')
        unique_sentences = []
        seen_sentences = set()
        
        for sentence in sentences:
            sentence_clean = sentence.strip().lower()
            if sentence_clean and sentence_clean not in seen_sentences and len(sentence_clean) > 10:
                unique_sentences.append(sentence.strip())
                seen_sentences.add(sentence_clean)
        
        # Восстанавливаем точки в конце предложений
        final_sentences = []
        for i, sentence in enumerate(unique_sentences):
            if not sentence.endswith('.') and not sentence.endswith(':') and not sentence.endswith(';'):
                if i < len(unique_sentences) - 1:  # Не последнее предложение
                    sentence += '.'
            final_sentences.append(sentence)
        
        return '. '.join(final_sentences)
    
    def _log_query(self, user_id: int, question: str, answer: str, chunks_count: int):
        """Логирование запроса пользователя"""
        try:
            from shared.models.query_log import QueryLog
            
            log_entry = QueryLog(
                user_id=user_id,
                query_text=question,
                response_text=answer,
                chunks_used=chunks_count,
                model_used="GigaChat"
            )
            
            self.db_session.add(log_entry)
            self.db_session.commit()
            
        except Exception as e:
            self.logger.error(f"Ошибка логирования запроса: {str(e)}")
    
    def health_check(self) -> Dict[str, bool]:
        """Проверка работоспособности всех компонентов"""
        return {
            'embeddings_model': self.embedding_model is not None,
            'llm_client': self.llm_client.health_check(),
            'database': self._check_database()
        }
    
    def _check_database(self) -> bool:
        """Проверка подключения к базе данных"""
        try:
            self.db_session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def _is_relevant_content(self, content: str, question: str) -> bool:
        """Проверка релевантности контента к вопросу"""
        content_lower = content.lower()
        question_lower = question.lower()
        
        # Исключаем технические части документов
        technical_markers = [
            'приложение', 'утверждаю', 'генеральный директор', 
            'система менеджмента', 'введено впервые', 'дата введения',
            'область применения', 'настоящее положение направлено',
            'акционерное общество', 'сибгазполимер'
        ]
        
        # Если содержит много технических маркеров, исключаем
        technical_count = sum(1 for marker in technical_markers if marker in content_lower)
        if technical_count > 2:
            return False
        
        # Проверяем наличие ключевых слов из вопроса
        question_words = set(word for word in question_lower.split() if len(word) > 2)
        content_words = set(content_lower.split())
        
        overlap = question_words & content_words
        
        # Минимум 2 общих слова или один точный ключевой термин
        if len(overlap) >= 2:
            return True
            
        # Проверяем точные ключевые термины
        key_terms = {
            'отпуск': ['отпуск', 'отпускные', 'отдых'],
            'зарплата': ['зарплата', 'заработная плата', 'оплата труда'],
            'выплаты': ['выплаты', 'выплата', 'начисления', 'премия'],
            'юбилей': ['юбилей', 'юбилейные', 'годовщина'],
            'больничный': ['больничный', 'нетрудоспособность'],
            'командировка': ['командировка', 'служебная поездка'],
            'увольнение': ['увольнение', 'расторжение договора']
        }
        
        for term_group in key_terms.values():
            question_has_term = any(term in question_lower for term in term_group)
            content_has_term = any(term in content_lower for term in term_group)
            
            if question_has_term and content_has_term:
                return True
        
            return False 