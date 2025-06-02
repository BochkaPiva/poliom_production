import logging
import re
from telegram import Update
from telegram.ext import ContextTypes

from services.shared.config import Config
from services.telegram_bot.bot.rag_service import RAGService

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, config: Config, rag_service: RAGService):
        self.config = config
        self.rag_service = rag_service

    def is_blocked_response(self, response: str) -> bool:
        """Проверяет, заблокирован ли ответ GigaChat"""
        blocked_phrases = [
            "Генеративные языковые модели не обладают собственным мнением",
            "разговоры на чувствительные темы могут быть ограничены",
            "разговоры на некоторые темы временно ограничены",
            "Как и любая языковая модель, GigaChat не обладает собственным мнением"
        ]
        return any(phrase in response for phrase in blocked_phrases)

    def extract_key_information(self, context: str, question: str) -> str:
        """Извлекает ключевую информацию из контекста для формирования ответа"""
        
        # Разбиваем контекст на источники
        sources = re.split(r'\[Источник \d+:', context)
        
        # Ключевые слова из вопроса для поиска релевантной информации
        question_words = set(re.findall(r'\b\w+\b', question.lower()))
        
        # Удаляем стоп-слова
        stop_words = {'в', 'на', 'с', 'по', 'для', 'от', 'до', 'из', 'к', 'о', 'об', 'и', 'или', 'а', 'но', 'что', 'как', 'когда', 'где', 'почему', 'какой', 'какая', 'какие', 'который', 'которая', 'которые'}
        question_words = question_words - stop_words
        
        relevant_info = []
        
        for source in sources[1:]:  # Пропускаем первый пустой элемент
            if not source.strip():
                continue
                
            # Извлекаем название документа
            doc_match = re.search(r'^([^\]]+)\]', source)
            doc_name = doc_match.group(1) if doc_match else "Документ"
            
            # Получаем текст источника
            source_text = source.split(']', 1)[-1].strip()
            
            # Ищем релевантные предложения
            sentences = re.split(r'[.!?]+', source_text)
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:  # Пропускаем слишком короткие предложения
                    continue
                    
                sentence_words = set(re.findall(r'\b\w+\b', sentence.lower()))
                
                # Проверяем пересечение с ключевыми словами вопроса
                if question_words & sentence_words:
                    relevant_info.append({
                        'text': sentence,
                        'source': doc_name,
                        'relevance': len(question_words & sentence_words)
                    })
        
        # Сортируем по релевантности
        relevant_info.sort(key=lambda x: x['relevance'], reverse=True)
        
        if not relevant_info:
            return None
            
        # Формируем ответ из наиболее релевантной информации
        response_parts = ["📋 **Информация из корпоративных документов:**\n"]
        
        used_sources = set()
        added_info = 0
        
        for info in relevant_info[:5]:  # Берем топ-5 наиболее релевантных
            if added_info >= 3:  # Ограничиваем количество пунктов
                break
                
            text = info['text']
            source = info['source']
            
            # Избегаем дублирования информации
            if text not in [item['text'] for item in relevant_info[:added_info]]:
                response_parts.append(f"• {text}")
                used_sources.add(source)
                added_info += 1
        
        if used_sources:
            response_parts.append(f"\n*Источники: {', '.join(used_sources)}*")
        
        return "\n".join(response_parts)

    def extract_specific_data_patterns(self, context: str, question: str) -> str:
        """Извлекает специфические паттерны данных (даты, числа, проценты и т.д.)"""
        
        patterns = {
            'dates': r'\b\d{1,2}[-./]\d{1,2}[-./]\d{2,4}\b|\b\d{1,2}[-е\s]*(?:число|числа)\b',
            'percentages': r'\b\d+(?:[.,]\d+)?%\b|\b\d+(?:[.,]\d+)?\s*процент[а-я]*\b',
            'money': r'\b\d+(?:\s?\d{3})*(?:[.,]\d+)?\s*(?:руб|рубл[ей]*|тыс|млн)\b',
            'time': r'\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*час[а-я]*\b',
            'periods': r'\b(?:ежемесячно|еженедельно|ежегодно|раз в месяц|два раза в месяц)\b'
        }
        
        found_data = []
        
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, context, re.IGNORECASE)
            if matches:
                found_data.extend(matches)
        
        if found_data:
            # Убираем дубликаты
            unique_data = list(set(found_data))
            return f"**Найденные данные:** {', '.join(unique_data)}"
        
        return None

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает входящие сообщения"""
        try:
            user_message = update.message.text
            user_id = update.effective_user.id
            
            logger.info(f"Получено сообщение от пользователя {user_id}: {user_message}")
            
            # Отправляем индикатор "печатает"
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            # Получаем ответ от RAG системы
            response = await self.rag_service.answer_question(user_message)
            
            # Проверяем, заблокирован ли ответ
            if self.is_blocked_response(response):
                logger.warning(f"Ответ заблокирован GigaChat для вопроса: {user_message}")
                
                # Получаем контекст из RAG системы для анализа
                try:
                    # Получаем релевантные чанки
                    chunks = await self.rag_service.search_relevant_chunks(user_message, limit=10)
                    
                    if chunks:
                        # Формируем контекст из чанков
                        context_parts = []
                        for i, chunk in enumerate(chunks, 1):
                            doc_title = chunk.get('document_title', 'Документ')
                            content = chunk.get('content', '')
                            context_parts.append(f"[Источник {i}: {doc_title}]\n{content}")
                        
                        full_context = "\n\n".join(context_parts)
                        
                        # Пытаемся извлечь ключевую информацию
                        extracted_info = self.extract_key_information(full_context, user_message)
                        
                        if extracted_info:
                            response = extracted_info
                            logger.info("Использована извлеченная информация из контекста")
                        else:
                            # Пытаемся найти специфические данные
                            specific_data = self.extract_specific_data_patterns(full_context, user_message)
                            if specific_data:
                                response = f"📊 **Информация из документов:**\n\n{specific_data}\n\n*Найдено в корпоративной документации*"
                                logger.info("Использованы извлеченные специфические данные")
                            else:
                                response = """❌ К сожалению, этот вопрос временно недоступен для обработки.

Попробуйте переформулировать вопрос или обратитесь к HR-отделу для получения подробной информации."""
                    else:
                        response = "❌ Информация по вашему запросу не найдена в корпоративных документах."
                        
                except Exception as e:
                    logger.error(f"Ошибка при извлечении контекста: {e}")
                    response = """❌ К сожалению, произошла ошибка при обработке запроса.

Попробуйте переформулировать вопрос или обратитесь к HR-отделу."""
            
            # Отправляем ответ
            await update.message.reply_text(
                response,
                parse_mode='Markdown'
            )
            
            logger.info(f"Отправлен ответ пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего запроса. Попробуйте позже."
            ) 