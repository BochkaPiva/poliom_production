# services/shared/utils/llm_client.py

import logging
import requests
import json
import time
import base64
import uuid
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    """Ответ от LLM"""
    text: str
    tokens_used: int
    model: str
    success: bool
    error: Optional[str] = None

class GigaChatClient:
    """Клиент для GigaChat с правильной OAuth аутентификацией"""
    
    def __init__(self, authorization_key: str):
        self.authorization_key = authorization_key
        self.oauth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        self.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        self.model = "GigaChat"
        
        # Токен доступа и время его истечения
        self.access_token = None
        self.token_expires_at = 0
        
    def _get_access_token(self) -> Optional[str]:
        """Получение Access token через OAuth"""
        try:
            # Проверяем, нужно ли обновить токен (с запасом в 5 минут)
            if self.access_token and time.time() < (self.token_expires_at - 300):
                return self.access_token
            
            # Генерируем уникальный RqUID
            rq_uid = str(uuid.uuid4())
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'RqUID': rq_uid,
                'Authorization': f'Basic {self.authorization_key}'
            }
            
            data = {
                'scope': 'GIGACHAT_API_PERS'
            }
            
            logger.info("Запрашиваем новый Access token от GigaChat...")
            
            response = requests.post(
                self.oauth_url,
                headers=headers,
                data=data,
                timeout=30,
                verify=False  # Отключаем проверку SSL для корпоративной сети
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                
                # Токен действует 30 минут
                self.token_expires_at = time.time() + 1800  # 30 минут
                
                logger.info("✅ Access token успешно получен")
                return self.access_token
            else:
                logger.error(f"Ошибка получения токена: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при получении Access token: {str(e)}")
            return None
    
    def _get_headers(self) -> Optional[Dict[str, str]]:
        """Получение заголовков для запроса с актуальным токеном"""
        access_token = self._get_access_token()
        if not access_token:
            return None
            
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def generate_response(self, 
                         prompt: str, 
                         max_tokens: int = 2500,
                         temperature: float = 0.7) -> LLMResponse:
        """
        Генерация ответа от GigaChat
        
        Args:
            prompt: Текст запроса
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации (0.0-1.0)
            
        Returns:
            LLMResponse: Ответ от модели
        """
        try:
            headers = self._get_headers()
            if not headers:
                return LLMResponse(
                    text="",
                    tokens_used=0,
                    model=self.model,
                    success=False,
                    error="Не удалось получить токен доступа"
                )
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
                verify=False  # Отключаем проверку SSL для корпоративной сети
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return LLMResponse(
                    text=data["choices"][0]["message"]["content"],
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                    model=self.model,
                    success=True
                )
            else:
                logger.error(f"GigaChat API error: {response.status_code} - {response.text}")
                return LLMResponse(
                    text="",
                    tokens_used=0,
                    model=self.model,
                    success=False,
                    error=f"API error: {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"Error calling GigaChat: {str(e)}")
            return LLMResponse(
                text="",
                tokens_used=0,
                model=self.model,
                success=False,
                error=str(e)
            )

class SimpleLLMClient:
    """Упрощенный клиент - только GigaChat"""
    
    def __init__(self, gigachat_authorization_key: str):
        self.gigachat = GigaChatClient(gigachat_authorization_key)
        logger.info("Инициализирован простой LLM клиент с GigaChat")
    
    def generate_answer(self, 
                       context: str, 
                       question: str,
                       max_tokens: int = 2500) -> LLMResponse:
        """
        Генерация ответа на основе контекста
        
        Args:
            context: Контекст из найденных документов
            question: Вопрос пользователя
            max_tokens: Максимальное количество токенов
            
        Returns:
            LLMResponse: Ответ от модели
        """
        # Формируем промпт для генерации ответа
        prompt = f"""Ты - справочная система по корпоративным документам. Твоя задача - предоставлять точную информацию из предоставленных документов.

КОНТЕКСТ ИЗ ДОКУМЕНТОВ:
{context}

ПРАВИЛА ОТВЕТА:
1. Используй ТОЛЬКО информацию из предоставленных документов
2. Если в документах есть точные числа, даты или фразы - цитируй их дословно
3. Не добавляй общую информацию или знания извне
4. Если информации нет в документах - так и скажи
5. Отвечай кратко и по существу
6. При упоминании конкретных дат или чисел - указывай их точно

ПРИМЕР ХОРОШЕГО ОТВЕТА:
Вопрос: "Какие установлены дни для расчетов?"
Ответ: "Согласно документу, установленными днями для расчетов с работниками являются 12-е и 27-е числа месяца."

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

ОТВЕТ:"""

        return self.gigachat.generate_response(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.1  # Очень низкая температура для максимальной точности
        )
    
    def health_check(self) -> bool:
        """Проверка работоспособности LLM"""
        try:
            response = self.gigachat.generate_response(
                prompt="Привет! Это тест.",
                max_tokens=50
            )
            return response.success
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False 