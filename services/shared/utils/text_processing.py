import os
import re
import logging
from typing import List, Optional
from pathlib import Path
import docx
import PyPDF2
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

# Настройки чанкирования
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))


def clean_text(text: str) -> str:
    """
    Очищает текст от лишних символов и нормализует пробелы.
    """
    if not text:
        return ""
    
    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\s+', ' ', text)
    
    # Удаляем специальные символы, оставляя только буквы, цифры и знаки препинания
    text = re.sub(r'[^\w\s\.,!?;:()\-—–«»""\']+', ' ', text)
    
    # Нормализуем пробелы
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Разбивает текст на чанки с перекрытием.
    """
    if not text:
        return []
    
    # Очищаем текст
    text = clean_text(text)
    
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Если это не последний чанк, пытаемся найти границу предложения
        if end < len(text):
            # Ищем ближайшую точку, восклицательный или вопросительный знак
            sentence_end = max(
                text.rfind('.', start, end),
                text.rfind('!', start, end),
                text.rfind('?', start, end)
            )
            
            # Если нашли границу предложения, используем её
            if sentence_end > start:
                end = sentence_end + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Следующий чанк начинается с учетом перекрытия
        start = end - overlap
        
        # Избегаем бесконечного цикла
        if start >= end:
            start = end
    
    return chunks


def extract_text_from_pdf(file_path: str) -> str:
    """
    Извлекает текст из PDF файла.
    """
    try:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Ошибка при извлечении текста из PDF {file_path}: {e}")
        return ""


def extract_text_from_docx(file_path: str) -> str:
    """
    Извлекает текст из DOCX файла.
    """
    try:
        doc = DocxDocument(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        logger.error(f"Ошибка при извлечении текста из DOCX {file_path}: {e}")
        return ""


def extract_text_from_txt(file_path: str) -> str:
    """
    Извлекает текст из TXT файла.
    """
    try:
        # Пробуем разные кодировки
        encodings = ['utf-8', 'cp1251', 'latin-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue
        
        # Если ни одна кодировка не подошла
        logger.error(f"Не удалось определить кодировку файла {file_path}")
        return ""
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении текста из TXT {file_path}: {e}")
        return ""


def extract_text_from_file(file_path: str) -> str:
    """
    Извлекает текст из файла в зависимости от его типа.
    """
    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        return ""
    
    file_extension = Path(file_path).suffix.lower()
    
    if file_extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension in ['.docx', '.doc']:
        return extract_text_from_docx(file_path)
    elif file_extension == '.txt':
        return extract_text_from_txt(file_path)
    else:
        logger.error(f"Неподдерживаемый тип файла: {file_extension}")
        return ""


def validate_file_type(filename: str) -> bool:
    """
    Проверяет, поддерживается ли тип файла.
    """
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    file_extension = Path(filename).suffix.lower()
    return file_extension in allowed_extensions


def get_file_info(file_path: str) -> dict:
    """
    Получает информацию о файле.
    """
    if not os.path.exists(file_path):
        return {}
    
    file_stat = os.stat(file_path)
    file_path_obj = Path(file_path)
    
    return {
        "filename": file_path_obj.name,
        "size": file_stat.st_size,
        "extension": file_path_obj.suffix.lower(),
        "created_at": file_stat.st_ctime,
        "modified_at": file_stat.st_mtime
    } 