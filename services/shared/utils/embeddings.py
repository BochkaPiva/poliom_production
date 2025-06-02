"""
Простейший сервис эмбеддингов без тяжелых зависимостей
"""

import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)

class SimpleEmbeddings:
    """
    Простая система эмбеддингов
    Только локальная модель - никаких сложностей!
    """
    
    def __init__(self):
        """Инициализация с локальной русской моделью"""
        logger.info("Загружаем локальную модель эмбеддингов...")
        
        try:
            # Используем более совместимую русскую модель
            self.model = SentenceTransformer('cointegrated/rubert-tiny2')
            self.model_name = "rubert-tiny2"
            self.embedding_dim = 312  # Размерность эмбеддингов для этой модели
            
            logger.info(f"Модель {self.model_name} успешно загружена!")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {str(e)}")
            raise
    
    def create_embedding(self, text: str) -> Optional[List[float]]:
        """
        Создание эмбеддинга для текста
        
        Args:
            text: Входной текст
            
        Returns:
            List[float]: Вектор эмбеддинга или None при ошибке
        """
        if not text or not text.strip():
            logger.warning("Пустой текст для создания эмбеддинга")
            return None
        
        try:
            # Очищаем текст
            clean_text = text.strip()
            
            # Создаем эмбеддинг
            embedding = self.model.encode(clean_text)
            
            # Конвертируем в список
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Ошибка создания эмбеддинга: {str(e)}")
            return None
    
    def create_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Создание эмбеддингов для списка текстов (батчевая обработка)
        
        Args:
            texts: Список текстов
            
        Returns:
            List[Optional[List[float]]]: Список эмбеддингов
        """
        if not texts:
            return []
        
        try:
            # Очищаем тексты
            clean_texts = [text.strip() for text in texts if text and text.strip()]
            
            if not clean_texts:
                return [None] * len(texts)
            
            # Создаем эмбеддинги батчем (быстрее)
            embeddings = self.model.encode(clean_texts)
        
            # Конвертируем в список списков
            result = []
            clean_idx = 0
            
            for original_text in texts:
                if original_text and original_text.strip():
                    result.append(embeddings[clean_idx].tolist())
                    clean_idx += 1
                else:
                    result.append(None)
        
            return result
            
        except Exception as e:
            logger.error(f"Ошибка создания батча эмбеддингов: {str(e)}")
            return [None] * len(texts)
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Вычисление косинусного сходства между эмбеддингами
        
        Args:
            embedding1: Первый эмбеддинг
            embedding2: Второй эмбеддинг
            
        Returns:
            float: Значение сходства от 0 до 1
        """
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Косинусное сходство
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            
            # Приводим к диапазону [0, 1]
            return max(0.0, min(1.0, (similarity + 1) / 2))
            
        except Exception as e:
            logger.error(f"Ошибка вычисления сходства: {str(e)}")
            return 0.0
    
    def get_model_info(self) -> dict:
        """Информация о модели"""
        return {
            'model_name': self.model_name,
            'embedding_dimension': self.embedding_dim,
            'type': 'local',
            'language': 'russian',
            'cost': 'free'
        }
    
    def health_check(self) -> bool:
        """Проверка работоспособности модели"""
        try:
            test_embedding = self.create_embedding("Тест")
            return test_embedding is not None and len(test_embedding) == self.embedding_dim
        except Exception:
            return False


# Для совместимости с новым кодом
class EmbeddingService(SimpleEmbeddings):
    """Алиас для совместимости"""
    
    def get_embedding(self, text: str) -> List[float]:
        """Совместимость с новым API"""
        result = self.create_embedding(text)
        return result if result is not None else [0.0] * self.embedding_dim
    
    def similarity(self, text1: str, text2: str) -> float:
        """Вычисляет схожесть между двумя текстами"""
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        return self.calculate_similarity(emb1, emb2) 