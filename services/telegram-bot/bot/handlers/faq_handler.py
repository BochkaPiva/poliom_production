#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAQ Handler для Telegram-бота POLIOM
Обработка статичного меню FAQ и интеграция с поиском
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
import logging
import sys
from pathlib import Path

# Добавляем путь к shared модулям
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

# Исправляем импорт на абсолютный
try:
    from bot.faq_data import FAQ_DATA, get_faq_sections, get_section_questions, get_answer, search_faq
except ImportError:
    # Fallback для случая, если модуль не найден
    FAQ_DATA = {}
    def get_faq_sections(): return []
    def get_section_questions(section): return []
    def get_answer(section, question): return None
    def search_faq(query): return []

try:
    from services.shared.utils.search_service import SearchService
    from services.shared.utils.llm_service import LLMService
except ImportError:
    # Fallback для тестирования
    class SearchService:
        def search(self, query, max_results=5):
            return {'results': []}
    
    class LLMService:
        async def format_search_answer(self, question, results):
            return f"Ответ на вопрос: {question}"
        
        async def handle_no_results(self, question):
            return f"К сожалению, не найдено информации по запросу: {question}"
        
        async def suggest_clarification(self, question):
            return f"Попробуйте переформулировать вопрос: {question}"

logger = logging.getLogger(__name__)

class FAQHandler:
    def __init__(self):
        self.search_service = SearchService()
        self.llm_service = LLMService()
    
    async def show_faq_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню FAQ"""
        keyboard = []
        
        # Создаем кнопки для каждого раздела
        sections = get_faq_sections()
        for i in range(0, len(sections), 2):
            row = []
            for j in range(2):
                if i + j < len(sections):
                    section = sections[i + j]
                    row.append(InlineKeyboardButton(
                        section, 
                        callback_data=f"faq_section:{section}"
                    ))
            keyboard.append(row)
        
        # Добавляем кнопки поиска и помощи
        keyboard.extend([
            [InlineKeyboardButton("🔍 Умный поиск", callback_data="smart_search")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = """🤖 **POLIOM HR Assistant**

📚 **Выберите раздел FAQ:**

Здесь вы найдете ответы на самые частые вопросы по трудовым отношениям, оплате труда, отпускам и другим важным темам.

🔍 **Умный поиск** - задайте любой вопрос своими словами, и я найду наиболее подходящий ответ в документах компании."""

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_section_questions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать вопросы в выбранном разделе"""
        query = update.callback_query
        await query.answer()
        
        section = query.data.split(":", 1)[1]
        questions = get_section_questions(section)
        
        if not questions:
            await query.edit_message_text("❌ Раздел не найден")
            return
        
        keyboard = []
        
        # Создаем кнопки для каждого вопроса
        for question in questions:
            keyboard.append([InlineKeyboardButton(
                f"❓ {question[:60]}..." if len(question) > 60 else f"❓ {question}",
                callback_data=f"faq_answer:{section}:{question}"
            )])
        
        # Кнопка "Назад"
        keyboard.append([InlineKeyboardButton("⬅️ Назад к разделам", callback_data="faq_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        section_description = FAQ_DATA[section]["description"]
        message_text = f"""📋 **{section}**

{section_description}

Выберите интересующий вас вопрос:"""
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать ответ на выбранный вопрос"""
        query = update.callback_query
        await query.answer()
        
        try:
            _, section, question = query.data.split(":", 2)
            answer_data = get_answer(section, question)
            
            if not answer_data:
                await query.edit_message_text("❌ Ответ не найден")
                return
            
            keyboard = [
                [InlineKeyboardButton("🔍 Найти похожие вопросы", callback_data=f"search_similar:{question}")],
                [InlineKeyboardButton("⬅️ Назад к вопросам", callback_data=f"faq_section:{section}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="faq_menu")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""❓ **{question}**

{answer_data['answer']}

📋 *{answer_data['source']}*"""
            
            await query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error showing answer: {e}")
            await query.edit_message_text("❌ Произошла ошибка при загрузке ответа")
    
    async def start_smart_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать умный поиск"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад к FAQ", callback_data="faq_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = """🔍 **Умный поиск**

Задайте любой вопрос своими словами, и я найду наиболее подходящий ответ в документах компании.

**Примеры вопросов:**
• Сколько дней отпуска положено?
• Как оплачивается работа в выходные?
• Какие документы нужны для приема на работу?
• Можно ли работать удаленно?

Просто напишите ваш вопрос следующим сообщением 👇"""
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Устанавливаем состояние ожидания вопроса
        context.user_data['waiting_for_search'] = True
    
    async def handle_search_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать поисковый запрос"""
        if not context.user_data.get('waiting_for_search'):
            return
        
        context.user_data['waiting_for_search'] = False
        user_question = update.message.text
        
        # Показываем индикатор печати
        await update.message.reply_chat_action("typing")
        
        try:
            # Сначала ищем в FAQ
            faq_results = search_faq(user_question)
            
            # Затем ищем в документах через SearchService
            search_results = self.search_service.search(user_question, max_results=3)
            
            if faq_results or search_results.get('results'):
                # Форматируем ответ с помощью LLM
                formatted_answer = await self.llm_service.format_search_answer(
                    user_question, 
                    search_results.get('results', [])
                )
                
                keyboard = [
                    [InlineKeyboardButton("🔍 Новый поиск", callback_data="smart_search")],
                    [InlineKeyboardButton("📚 FAQ", callback_data="faq_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Добавляем результаты FAQ если есть
                if faq_results:
                    faq_section = "\n\n📚 **Похожие вопросы в FAQ:**\n"
                    for result in faq_results[:2]:  # Показываем только 2 лучших результата
                        faq_section += f"• {result['question']}\n"
                    formatted_answer += faq_section
                
                await update.message.reply_text(
                    formatted_answer,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                # Если ничего не найдено
                keyboard = [
                    [InlineKeyboardButton("🔍 Попробовать еще раз", callback_data="smart_search")],
                    [InlineKeyboardButton("📚 Посмотреть FAQ", callback_data="faq_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "❌ К сожалению, я не нашел информации по вашему вопросу.\n\n"
                    "Попробуйте:\n"
                    "• Переформулировать вопрос\n"
                    "• Использовать другие ключевые слова\n"
                    "• Посмотреть разделы FAQ",
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error in search: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при поиске. Попробуйте позже."
            )
    
    async def search_similar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Найти похожие вопросы"""
        query = update.callback_query
        await query.answer()
        
        question = query.data.split(":", 1)[1]
        
        # Ищем похожие вопросы в FAQ
        faq_results = search_faq(question)
        
        if len(faq_results) <= 1:  # Исключаем текущий вопрос
            await query.edit_message_text(
                "❌ Похожие вопросы не найдены",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Назад", callback_data="faq_menu")
                ]])
            )
            return
        
        keyboard = []
        for result in faq_results[1:4]:  # Показываем до 3 похожих вопросов
            keyboard.append([InlineKeyboardButton(
                f"❓ {result['question'][:50]}...",
                callback_data=f"faq_answer:{result['section']}:{result['question']}"
            )])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад к FAQ", callback_data="faq_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🔍 **Похожие вопросы для:** {question[:50]}...\n\nВыберите интересующий вопрос:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать справку"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад к FAQ", callback_data="faq_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        help_text = """❓ **Справка по боту**

🤖 **Возможности бота:**
• 📚 Просмотр FAQ по разделам
• 🔍 Умный поиск по документам
• 📋 Получение точных ответов с источниками

🔍 **Как пользоваться поиском:**
1. Нажмите "Умный поиск"
2. Задайте вопрос своими словами
3. Получите ответ с указанием источника

📚 **Разделы FAQ:**
• 💰 Оплата труда - зарплата, премии, надбавки
• ⏰ Рабочее время - график, отпуска, переработки
• 🏠 Дистанционная работа - удаленка, требования
• 🤝 Социальная поддержка - помощь, компенсации
• 🏆 Поощрения - награды, благодарности
• ⚖️ Трудовые отношения - прием, увольнение
• 🛡️ Охрана труда - безопасность, медосмотры

💡 **Совет:** Если не нашли ответ в FAQ, используйте умный поиск - он найдет информацию во всех документах компании."""
        
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

# Функции для регистрации обработчиков
def register_faq_handlers(application):
    """Регистрация обработчиков FAQ"""
    faq_handler = FAQHandler()
    
    # Команды
    application.add_handler(CommandHandler("faq", faq_handler.show_faq_menu))
    application.add_handler(CommandHandler("help", faq_handler.show_help))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(
        faq_handler.show_faq_menu, pattern="^faq_menu$"
    ))
    application.add_handler(CallbackQueryHandler(
        faq_handler.show_section_questions, pattern="^faq_section:"
    ))
    application.add_handler(CallbackQueryHandler(
        faq_handler.show_answer, pattern="^faq_answer:"
    ))
    application.add_handler(CallbackQueryHandler(
        faq_handler.start_smart_search, pattern="^smart_search$"
    ))
    application.add_handler(CallbackQueryHandler(
        faq_handler.search_similar, pattern="^search_similar:"
    ))
    application.add_handler(CallbackQueryHandler(
        faq_handler.show_help, pattern="^help$"
    ))
    
    return faq_handler 