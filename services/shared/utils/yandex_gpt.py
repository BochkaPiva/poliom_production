import os
import json
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class YandexGPTClient:
    """
    Клиент для работы с YandexGPT API.
    """
    
    def __init__(self, api_key: Optional[str] = None, folder_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("YANDEX_API_KEY")
        self.folder_id = folder_id or os.getenv("YANDEX_FOLDER_ID")
        self.base_url = "https://llm.api.cloud.yandex.net/foundationModels/v1"
        
        if not self.api_key:
            raise ValueError("YandexGPT API key не найден в переменных окружения")
        if not self.folder_id:
            raise ValueError("Yandex Folder ID не найден в переменных окружения")
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Выполняет запрос к YandexGPT API.
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к YandexGPT: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка при парсинге ответа YandexGPT: {e}")
            return None
    
    def generate_answer(
        self, 
        context: str, 
        question: str, 
        max_tokens: int = 2000,
        temperature: float = 0.3
    ) -> Optional[str]:
        """
        Генерирует ответ на основе контекста и вопроса.
        """
        system_prompt = """Ты - корпоративный помощник, который отвечает на вопросы сотрудников на основе предоставленной документации.

Правила:
1. Отвечай только на основе предоставленного контекста
2. Если в контексте нет информации для ответа, честно скажи об этом
3. Отвечай кратко и по существу
4. Используй профессиональный, но дружелюбный тон
5. Если нужно, предложи обратиться к конкретному отделу или специалисту

Контекст из документации:
{context}

Вопрос сотрудника: {question}

Ответ:"""

        prompt = system_prompt.format(context=context, question=question)
        
        data = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": str(max_tokens)
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }
        
        response = self._make_request("completion", data)
        
        if response and "result" in response:
            alternatives = response["result"].get("alternatives", [])
            if alternatives:
                return alternatives[0]["message"]["text"].strip()
        
        logger.error("Не удалось получить ответ от YandexGPT")
        return None
    
    def summarize_text(self, text: str, max_tokens: int = 500) -> Optional[str]:
        """
        Создает краткое резюме текста.
        """
        prompt = f"""Создай краткое резюме следующего текста на русском языке. 
Выдели основные моменты и ключевую информацию:

{text}

Резюме:"""
        
        data = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": str(max_tokens)
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }
        
        response = self._make_request("completion", data)
        
        if response and "result" in response:
            alternatives = response["result"].get("alternatives", [])
            if alternatives:
                return alternatives[0]["message"]["text"].strip()
        
        return None
    
    def extract_keywords(self, text: str) -> Optional[str]:
        """
        Извлекает ключевые слова из текста.
        """
        prompt = f"""Извлеки ключевые слова и фразы из следующего текста. 
Верни их через запятую:

{text}

Ключевые слова:"""
        
        data = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.1,
                "maxTokens": "200"
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }
        
        response = self._make_request("completion", data)
        
        if response and "result" in response:
            alternatives = response["result"].get("alternatives", [])
            if alternatives:
                return alternatives[0]["message"]["text"].strip()
        
        return None
    
    def check_relevance(self, context: str, question: str) -> bool:
        """
        Проверяет, релевантен ли контекст для ответа на вопрос.
        """
        prompt = f"""Определи, содержит ли предоставленный контекст информацию, 
необходимую для ответа на вопрос. Ответь только "ДА" или "НЕТ".

Контекст: {context}

Вопрос: {question}

Ответ:"""
        
        data = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.1,
                "maxTokens": "10"
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }
        
        response = self._make_request("completion", data)
        
        if response and "result" in response:
            alternatives = response["result"].get("alternatives", [])
            if alternatives:
                answer = alternatives[0]["message"]["text"].strip().upper()
                return "ДА" in answer
        
        return False 