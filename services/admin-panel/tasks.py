"""
Celery задачи для обработки документов
ОБНОВЛЕНО: Использует единый процессор документов
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Добавляем путь к shared модулям
current_dir = Path(__file__).parent
services_dir = current_dir.parent
sys.path.insert(0, str(services_dir))

from celery import Celery
from sqlalchemy.orm import sessionmaker

# Импортируем shared модули
from shared.models.database import engine
from shared.models import Document, DocumentChunk

# Импортируем ЕДИНЫЙ процессор документов
from document_processor_unified import process_document_unified

# Импортируем Celery app
from celery_app import app

# Создаем сессию базы данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.task(bind=True)
def process_document(self, document_id: int):
    """
    Обработка документа через ЕДИНЫЙ процессор
    Надежная обработка с улучшенным алгоритмом чанкинга
    """
    logger.info(f"Celery task: начинаем обработку документа {document_id}")
    
    try:
        # Используем единый процессор с безопасным режимом
        result = process_document_unified(document_id, use_safe_mode=True)
        
        logger.info(f"Celery task: результат обработки документа {document_id}: {result['status']}")
        
        if result["status"] == "completed":
            logger.info(f"Celery task: документ {document_id} успешно обработан. Создано {result['chunks_created']} чанков")
        else:
            logger.error(f"Celery task: ошибка обработки документа {document_id}: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        error_msg = f"Celery task: критическая ошибка обработки документа {document_id}: {str(e)}"
        logger.error(error_msg)
        
        return {
            "status": "failed",
            "document_id": document_id,
            "error": str(e)
        }


@app.task
def cleanup_failed_documents():
    """
    Периодическая задача для очистки неудачно обработанных документов
    """
    db = SessionLocal()
    
    try:
        # Находим документы со статусом "failed" старше 24 часов
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        failed_documents = db.query(Document).filter(
            Document.processing_status == "failed",
            Document.updated_at < cutoff_time
        ).all()
        
        cleaned_count = 0
        for document in failed_documents:
            try:
                # Удаляем файл с диска
                file_path = Path(document.file_path)
                if file_path.exists():
                    file_path.unlink()
                
                # Удаляем документ из базы данных
                db.delete(document)
                cleaned_count += 1
                
            except Exception as e:
                logger.error(f"Ошибка очистки документа {document.id}: {str(e)}")
                continue
        
        db.commit()
        logger.info(f"Очищено {cleaned_count} неудачно обработанных документов")
        
        return {"cleaned_documents": cleaned_count}
        
    except Exception as e:
        logger.error(f"Ошибка очистки неудачных документов: {str(e)}")
        return {"error": str(e)}
        
    finally:
        db.close() 