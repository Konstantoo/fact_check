#!/usr/bin/env python3
"""
Telegram-бот для проверки фактов и анализа статей
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Добавляем текущую директорию в путь для импорта модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_config import Config
from services.fact_checker_service import FactCheckerService
from services.perplexity_service import PerplexityService
from services.user_service import UserService
from services.payment_service import PaymentService
from services.deep_research_service import DeepResearchService
from utils.logger import setup_logger

# Настройка логирования
logger = setup_logger(__name__)

class TelegramFactCheckerBot:
    """Основной класс Telegram-бота для проверки фактов"""
    
    def __init__(self):
        self.config = Config()
        self.config.validate()
        
        # Инициализация сервисов
        self.fact_checker_service = FactCheckerService(self.config.PERPLEXITY_API_KEY)
        self.perplexity_service = PerplexityService(self.config.PERPLEXITY_API_KEY)
        self.user_service = UserService()
        self.payment_service = PaymentService(self.config.YOOKASSA_SHOP_ID, self.config.YOOKASSA_SECRET_KEY)
        self.deep_research_service = DeepResearchService()
        
        # Создаем приложение
        self.application = Application.builder().token(self.config.TELEGRAM_TOKEN).build()
        
        # Регистрируем обработчики
        self._register_handlers()
    
    def _register_handlers(self):
        """Регистрация обработчиков команд и сообщений"""
        # Команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("promo", self.promo_command))
        
        # Обработчики сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработчики callback-запросов
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Пользователь"
        
        logger.info(f"Пользователь {username} (ID: {user_id}) запустил бота")
        
        # Регистрируем пользователя
        self.user_service.register_user(user_id, username)
        
        # Получаем статистику пользователя
        user_stats = self.user_service.get_user_stats(user_id)
        
        welcome_text = f"""
🔍 Добро пожаловать!

{username}, я помогу проверить факты и проанализировать статьи.

Статистика:
• Сегодня: {user_stats['daily_requests']}/{user_stats['daily_limit']}
• Всего: {user_stats['total_requests']}
• Баланс: {user_stats['balance']} запросов

Выберите действие:
        """
        
        keyboard = [
            [InlineKeyboardButton("📰 Анализ статьи", callback_data="analyze_article")],
            [InlineKeyboardButton("🔍 Проверка утверждения", callback_data="check_fact")],
            [InlineKeyboardButton("📊 Мои запросы", callback_data="user_stats")],
            [InlineKeyboardButton("💳 Купить запросы", callback_data="buy_requests")],
            [InlineKeyboardButton("🎁 Промо-код", callback_data="promo_code")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🔍 Помощь

Анализ статьи:
• Отправьте ссылку или текст
• Получите разбор достоверности и источников

Проверка утверждения:
• Напишите фразу для проверки
• Получите оценку факта и источники

Дополнительно:
• Покупка запросов: пакеты 10/50/100/500
• Промо-код "42" — +5 запросов
• Статистика использования

Команды:
/start — главное меню
/help — справка
/promo — промо-код

Ограничения:
• Бесплатно 3 запроса/день
• Платные пакеты — без лимитов
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def promo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /promo"""
        await self.show_promo_code_input(update, context)
    
    async def show_promo_code_input(self, update_or_query, context: ContextTypes.DEFAULT_TYPE):
        """Показать интерфейс ввода промо-кода"""
        # Получаем user_id в зависимости от типа объекта
        if hasattr(update_or_query, 'effective_user'):
            user_id = update_or_query.effective_user.id
        else:
            # Это CallbackQuery
            user_id = update_or_query.from_user.id
        
        # Устанавливаем флаг ожидания промо-кода
        context.user_data['waiting_promo_code'] = True
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение в зависимости от типа объекта
        if hasattr(update_or_query, 'message'):
            # Это Update
            await update_or_query.message.reply_text(
                "🎁 Введите промо-код\n\nНапишите промо-код для получения бонусных запросов.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Это CallbackQuery
            await update_or_query.message.reply_text(
                "🎁 Введите промо-код\n\nНапишите промо-код для получения бонусных запросов.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        logger.info(f"Получено сообщение от пользователя {user_id}: {message_text[:100]}...")
        
        try:
            # Проверяем, ожидается ли промо-код
            if context.user_data.get('waiting_promo_code'):
                await self.handle_promo_code(update, context)
                return
            
            # Проверяем режим работы
            mode = context.user_data.get('mode')
            
            if mode == 'analyze_article':
                await self.handle_article_analysis(update, context)
            elif mode == 'check_fact':
                await self.handle_fact_check(update, context)
            elif message_text.startswith('http'):
                # Автоматически анализируем ссылку
                await self.handle_article_analysis(update, context)
            else:
                # Показываем главное меню
                await self.show_main_menu(update, context)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего запроса. Попробуйте еще раз.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
    
    async def handle_promo_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода промо-кода"""
        user_id = update.effective_user.id
        promo_code = update.message.text.strip()
        
        # Сбрасываем флаг ожидания
        context.user_data['waiting_promo_code'] = False
        
        # Применяем промо-код
        result = self.user_service.apply_promo_code(user_id, promo_code)
        
        if result['success']:
            # Получаем обновленную статистику
            user_stats = self.user_service.get_user_stats(user_id)
            
            await update.message.reply_text(
                f"🎉 Промо-код применен успешно!\n\n"
                f"✅ Добавлено запросов: {result['added_requests']}\n"
                f"📊 Текущий баланс: {user_stats['balance']} запросов",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка применения промо-кода\n\n{result['message']}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
    
    async def handle_article_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка анализа статьи"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Проверяем лимиты
        if not self.user_service.check_daily_limit(user_id):
            await update.message.reply_text(
                "❌ Достигнут дневной лимит запросов\n\n"
                "Купите дополнительные запросы или попробуйте завтра.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💳 Купить запросы", callback_data="buy_requests"),
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        # Сбрасываем режим
        context.user_data['mode'] = None
        
        try:
            # Показываем индикатор загрузки
            loading_message = await update.message.reply_text("🔍 Анализирую статью...")
            logger.info(f"Начинаем анализ для пользователя {user_id}: {message_text[:100]}...")
            logger.info(f"Полное сообщение от пользователя: '{message_text}'")
            
            # Анализируем статью
            if message_text.startswith('http'):
                # Это ссылка
                logger.info(f"Анализируем ссылку через Perplexity API: '{message_text}'")
                analysis = await self.perplexity_service.analyze_article(message_text)
                logger.info(f"Анализ завершен, результат: {str(analysis)[:200]}...")
            else:
                # Это текст
                logger.info("Анализируем текст через Perplexity API...")
                analysis = await self.perplexity_service.analyze_text(message_text)
                logger.info(f"Анализ завершен, результат: {str(analysis)[:200]}...")
            
            # Учитываем запрос
            self.user_service.make_request(user_id)
            
            # Удаляем сообщение о загрузке
            await loading_message.delete()
            
            # Сохраняем контекст для Deep Research
            context.user_data['last_topic'] = message_text
            context.user_data['last_analysis'] = analysis
            
            # Форматируем ответ
            from utils.response_formatter import ResponseFormatter
            formatter = ResponseFormatter()
            formatted_analysis = formatter.format_analysis(analysis)
            
            # Разбиваем длинные сообщения
            if len(formatted_analysis) > 4000:
                # Отправляем по частям
                parts = [formatted_analysis[i:i+4000] for i in range(0, len(formatted_analysis), 4000)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await update.message.reply_text(part, parse_mode='Markdown')
                    else:
                        await update.message.reply_text(part, parse_mode='Markdown')
            else:
                await update.message.reply_text(formatted_analysis, parse_mode='Markdown')
            
            # Показываем меню после анализа
            user_stats = self.user_service.get_user_stats(user_id)
            is_free = self.user_service.can_use_deep_research(user_id)
            deep_research_text = "🔬 Deep Research (БЕСПЛАТНО!)" if is_free else "🔬 Deep Research (449₽)"
            
            keyboard = [
                [InlineKeyboardButton(deep_research_text, callback_data="deep_research")],
                [InlineKeyboardButton("📰 Анализ другой статьи", callback_data="analyze_article")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Добавляем пояснение о Deep Research
            explanation_text = "Что дальше?\n\n"
            if is_free:
                explanation_text += "🔬 Deep Research — углубленный анализ с дополнительными источниками\n"
                explanation_text += "✅ Одна бесплатная попытка, далее 449₽ за исследование"
            else:
                explanation_text += "🔬 Deep Research — углубленный анализ с дополнительными источниками\n"
                explanation_text += "💰 Стоимость: 449₽ за исследование"
            
            await update.message.reply_text(
                explanation_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при анализе статьи: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при анализе статьи. Попробуйте еще раз.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
    
    async def handle_fact_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка проверки факта"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Проверяем лимиты
        if not self.user_service.check_daily_limit(user_id):
            await update.message.reply_text(
                "❌ **Достигнут дневной лимит запросов**\n\n"
                "Купите дополнительные запросы или попробуйте завтра.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💳 Купить запросы", callback_data="buy_requests"),
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]]),
                parse_mode='Markdown'
            )
            return
        
        # Сбрасываем режим
        context.user_data['mode'] = None
        
        try:
            # Показываем индикатор загрузки
            loading_message = await update.message.reply_text("🔍 Проверяю факт...")
            
            # Проверяем факт
            fact_check = await self.fact_checker_service.check_fact(message_text)
            
            # Учитываем запрос
            self.user_service.make_request(user_id)
            
            # Удаляем сообщение о загрузке
            await loading_message.delete()
            
            # Форматируем ответ
            from utils.response_formatter import ResponseFormatter
            formatter = ResponseFormatter()
            formatted_fact_check = formatter.format_fact_check(fact_check)
            
            # Сохраняем контекст для Deep Research по утверждению
            context.user_data['last_topic'] = f"Факт-чек утверждения: {message_text[:200]}"
            context.user_data['last_analysis'] = formatted_fact_check
            
            # Разбиваем длинные сообщения
            if len(formatted_fact_check) > 4000:
                # Отправляем по частям
                parts = [formatted_fact_check[i:i+4000] for i in range(0, len(formatted_fact_check), 4000)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await update.message.reply_text(part, parse_mode='Markdown')
                    else:
                        await update.message.reply_text(part, parse_mode='Markdown')
            else:
                await update.message.reply_text(formatted_fact_check, parse_mode='Markdown')
            
            # Показываем меню после проверки (с Deep Research)
            is_free = self.user_service.can_use_deep_research(user_id)
            deep_research_text = "🔬 Deep Research (БЕСПЛАТНО!)" if is_free else "🔬 Deep Research (449₽)"
            keyboard = [
                [InlineKeyboardButton("🔍 Проверить другое утверждение", callback_data="check_fact")],
                [InlineKeyboardButton(deep_research_text, callback_data="deep_research")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "**Что дальше?**",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при проверке факта: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при проверке факта. Попробуйте еще раз.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        logger.info(f"Обработка callback: {data} от пользователя {user_id}")
        
        if data == "analyze_article":
            await self.start_article_analysis(query, context)
        elif data == "check_fact":
            await self.start_fact_check(query, context)
        elif data == "user_stats":
            await self.show_user_stats(query, context)
        elif data == "buy_requests":
            await self.show_payment_options(query, context)
        elif data == "promo_code":
            await self.show_promo_code_input(query, context)
        elif data == "help":
            await self.show_help(query, context)
        elif data == "main_menu":
            await self.show_main_menu(query, context)
        elif data == "deep_research":
            await self.handle_deep_research(query, context)
        elif data == "confirm_deep_research":
            await self.confirm_deep_research(query, context)
        elif data.startswith("buy_"):
            await self.handle_payment_selection(query, context, data)
        else:
            await query.edit_message_text("❌ Неизвестная команда")
    
    async def start_article_analysis(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Начать анализ статьи"""
        context.user_data['mode'] = 'analyze_article'
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📰 **Анализ статьи**\n\n"
            "Отправьте ссылку на статью или скопируйте текст для анализа.\n\n"
            "Я проанализирую:\n"
            "• Достоверность информации\n"
            "• Верные и спорные утверждения\n"
            "• Качество источников\n"
            "• Объективность подачи",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def start_fact_check(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Начать проверку факта"""
        context.user_data['mode'] = 'check_fact'
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔍 **Проверка утверждения**\n\n"
            "Напишите утверждение для проверки.\n\n"
            "Я проверю:\n"
            "• Истинность утверждения\n"
            "• Уровень научного консенсуса\n"
            "• Надежность источников\n"
            "• Контекст и оговорки",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_user_stats(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Показать статистику пользователя"""
        user_id = query.from_user.id
        user_stats = self.user_service.get_user_stats(user_id)
        
        stats_text = f"""
📊 **Ваша статистика**

**Запросы сегодня:**
{user_stats['daily_requests']}/{user_stats['daily_limit']}

**Общая статистика:**
💳 Всего запросов: {user_stats['total_requests']}
💰 Баланс: {user_stats['balance']} запросов

**Лимиты:**
📅 Дневной лимит: {user_stats['daily_limit']} запросов
🔄 Сброс лимита: завтра в 00:00
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_payment_options(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Показать варианты оплаты"""
        prices = {
            "buy_10": {"price": 100, "requests": 10},
            "buy_50": {"price": 400, "requests": 50},
            "buy_100": {"price": 700, "requests": 100},
            "buy_500": {"price": 3000, "requests": 500}
        }
        
        keyboard = []
        for key, value in prices.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"💳 {value['requests']} запросов - {value['price']}₽",
                    callback_data=key
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💳 **Покупка запросов**\n\n"
            "Выберите пакет запросов для покупки:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_payment_selection(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        """Обработка выбора пакета запросов"""
        prices = {
            "buy_10": {"price": 100, "requests": 10},
            "buy_50": {"price": 400, "requests": 50},
            "buy_100": {"price": 700, "requests": 100},
            "buy_500": {"price": 3000, "requests": 500}
        }
        
        if data not in prices:
            await query.edit_message_text("❌ Неверный пакет запросов")
            return
        
        user_id = query.from_user.id
        price_info = prices[data]
        
        try:
            # Создаем платеж
            payment = await self.payment_service.create_payment(
                user_id=user_id,
                amount=price_info['price'],
                description=f"Покупка {price_info['requests']} запросов"
            )
            
            if payment:
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"💳 **Платеж создан**\n\n"
                    f"Сумма: {price_info['price']}₽\n"
                    f"Запросов: {price_info['requests']}\n\n"
                    f"Ссылка для оплаты:\n{payment['confirmation_url']}\n\n"
                    f"После оплаты запросы будут автоматически добавлены к вашему балансу.",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ Ошибка создания платежа. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                    ]])
                )
                
        except Exception as e:
            logger.error(f"Ошибка при создании платежа: {e}")
            await query.edit_message_text(
                "❌ Ошибка создания платежа. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
    
    async def show_help(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Показать справку"""
        help_text = """
🔍 **Помощь по использованию бота**

**Основные функции:**

📰 **Анализ статьи**
• Отправьте ссылку на статью или скопируйте текст
• Получите детальный анализ достоверности
• Узнайте о верных и спорных утверждениях

🔍 **Проверка утверждения**
• Напишите утверждение для проверки
• Получите оценку достоверности
• Узнайте уровень научного консенсуса

**Дополнительные возможности:**

💳 **Покупка запросов**
• Расширьте лимит запросов
• Доступны пакеты на 10, 50, 100, 500 запросов

🎁 **Промо-коды**
• Используйте промо-коды для получения бонусных запросов
• Код "42" дает 5 дополнительных запросов

📊 **Статистика**
• Отслеживайте использование запросов
• Проверяйте дневные лимиты

**Ограничения:**
• Бесплатно: 3 запроса в день
• Платные пакеты: без дневных ограничений
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_main_menu(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню"""
        user_id = query.from_user.id
        username = query.from_user.username or "Пользователь"
        
        # Получаем статистику пользователя
        user_stats = self.user_service.get_user_stats(user_id)
        
        welcome_text = f"""
🔍 **Главное меню**

Привет, {username}!

**Ваша статистика:**
📊 Запросов сегодня: {user_stats['daily_requests']}/{user_stats['daily_limit']}
💳 Всего запросов: {user_stats['total_requests']}
💰 Баланс: {user_stats['balance']} запросов

**Выберите действие:**
        """
        
        keyboard = [
            [InlineKeyboardButton("📰 Анализ статьи", callback_data="analyze_article")],
            [InlineKeyboardButton("🔍 Проверка утверждения", callback_data="check_fact")],
            [InlineKeyboardButton("📊 Мои запросы", callback_data="user_stats")],
            [InlineKeyboardButton("💳 Купить запросы", callback_data="buy_requests")],
            [InlineKeyboardButton("🎁 Промо-код", callback_data="promo_code")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_deep_research(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Обработка запроса на Deep Research"""
        user_id = query.from_user.id
        
        # Логируем имеющийся контекст
        try:
            logger.info(f"Deep Research user_data keys: {list(context.user_data.keys())}")
        except Exception:
            pass
        
        # Проверяем, есть ли контекст для Deep Research
        if not context.user_data.get('last_analysis'):
            # Если есть только тема, используем её как контекст
            fallback_topic = context.user_data.get('last_topic')
            if fallback_topic:
                context.user_data['last_analysis'] = (
                    f"Исходные данные получены из последнего действия пользователя.\n"
                    f"Тема: {fallback_topic}. Проведи углублённое исследование по этой теме, \n"
                    f"найди дополнительные независимые источники, статистику и экспертные мнения."
                )
            else:
                await query.edit_message_text(
                    "❌ Нет данных для Deep Research. Сначала выполните анализ статьи или проверку утверждения.",
                    reply_markup=InlineKeyboardMarkup([[ 
                        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                    ]])
                )
                return
        
        # Проверяем, может ли пользователь использовать Deep Research
        if not self.user_service.can_use_deep_research(user_id):
            user_stats = self.user_service.get_user_stats(user_id)
            if user_stats['balance'] < 449:
                await query.edit_message_text(
                    "❌ **Недостаточно запросов для Deep Research**\n\n"
                    "Требуется: 449 запросов\n"
                    f"У вас: {user_stats['balance']} запросов\n\n"
                    "Купите дополнительные запросы или используйте обычный анализ.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("💳 Купить запросы", callback_data="buy_requests"),
                        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                    ]]),
                    parse_mode='Markdown'
                )
                return
            else:
                # Списываем 449 запросов
                self.user_service.make_request(user_id, 449)
        
        # Показываем подтверждение
        is_free = self.user_service.can_use_deep_research(user_id)
        cost_text = "БЕСПЛАТНО" if is_free else "449 запросов"
        button_text = "✅ Подтвердить (БЕСПЛАТНО)" if is_free else "✅ Подтвердить (449₽)"
        
        keyboard = [
            [InlineKeyboardButton(button_text, callback_data="confirm_deep_research")],
            [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔬 **Deep Research**\n\n"
            "Глубокое исследование темы с расширенным анализом:\n\n"
            "• Детальный анализ всех аспектов\n"
            "• Множественные источники\n"
            "• Экспертная оценка\n"
            "• Подробные выводы\n\n"
            f"**Стоимость: {cost_text}**\n\n"
            "Продолжить?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def confirm_deep_research(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение Deep Research"""
        user_id = query.from_user.id
        
        try:
            # Проверяем, может ли пользователь использовать Deep Research
            is_free = self.user_service.can_use_deep_research(user_id)
            
            if not is_free:
                # Проверяем баланс для платного использования
                user_stats = self.user_service.get_user_stats(user_id)
                if user_stats['balance'] < 449:
                    await query.edit_message_text(
                        "❌ Недостаточно запросов для Deep Research",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                        ]])
                    )
                    return
                # Списываем запросы
                self.user_service.make_request(user_id, cost=449)
            
            # Показываем индикатор загрузки с временем
            await query.edit_message_text(
                "🔬 Запускаю Глубокое Исследование...\n\n"
                "⏱️ Ожидаемое время: 3-4 минуты\n"
                "🔍 Анализирую сотни источников...\n\n"
                "⏳ Пожалуйста, подождите..."
            )
            
            # Проводим Deep Research
            topic = context.user_data.get('last_topic')
            initial_analysis = context.user_data.get('last_analysis')
            
            logger.info(f"Начинаем Deep Research для пользователя {user_id}")
            logger.info(f"Тема: {topic}")
            logger.info(f"Начальный анализ: {initial_analysis[:100]}...")
            
            import time
            start_time = time.time()
            
            try:
                # Создаем задачу для Deep Research
                deep_research_task = asyncio.create_task(
                    self.deep_research_service.conduct_deep_research(topic, initial_analysis)
                )
                
                # Показываем промежуточные обновления
                status_messages = [
                    "🔍 Ищу независимые источники...",
                    "📊 Анализирую экспертные мнения...",
                    "📈 Собираю статистические данные...",
                    "🌍 Проверяю международные источники...",
                    "⚖️ Ищу альтернативные точки зрения...",
                    "🎯 Формирую заключение..."
                ]
                
                message_index = 0
                while not deep_research_task.done():
                    await asyncio.sleep(30)  # Обновляем каждые 30 секунд
                    if not deep_research_task.done() and message_index < len(status_messages):
                        await query.edit_message_text(
                            f"🔬 Глубокое Исследование...\n\n"
                            f"⏱️ Прошло: {int(time.time() - start_time)} секунд\n"
                            f"📊 {status_messages[message_index]}\n\n"
                            f"⏳ Пожалуйста, подождите..."
                        )
                        message_index += 1
                
                deep_research_result = await deep_research_task
                end_time = time.time()
                duration = int(end_time - start_time)
                
                logger.info(f"Deep Research завершен за {duration} секунд")
                
            except Exception as e:
                logger.error(f"Ошибка при проведении Deep Research: {str(e)}")
                await query.edit_message_text(
                    f"❌ **Ошибка при проведении Deep Research**\n\n"
                    f"Произошла ошибка: {str(e)}\n\n"
                    f"Попробуйте позже или обратитесь в поддержку."
                )
                return
            
            # Отмечаем использование Deep Research
            self.user_service.use_deep_research(user_id)
            
            # Форматируем результат с информацией о времени
            from utils.response_formatter import ResponseFormatter
            formatter = ResponseFormatter()
            
            # Добавляем заголовок с информацией о времени выполнения
            header = f"🔬 **DEEP RESEARCH ЗАВЕРШЕН**\n\n"
            header += f"⏱️ **Время выполнения:** {duration} секунд\n"
            header += f"🧠 **Модель:** Perplexity Sonar (оптимизированная)\n"
            header += f"📊 **Тип анализа:** углубленное исследование\n\n"
            header += "---\n\n"
            
            formatted_result = header + formatter.format_deep_research(deep_research_result)
            
            # Разбиваем длинные сообщения
            if len(formatted_result) > 4000:
                parts = [formatted_result[i:i+4000] for i in range(0, len(formatted_result), 4000)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await query.edit_message_text(part, parse_mode='Markdown')
                    else:
                        await query.message.reply_text(part, parse_mode='Markdown')
            else:
                await query.edit_message_text(formatted_result, parse_mode='Markdown')
            
            # Показываем меню после Deep Research
            keyboard = [
                [InlineKeyboardButton("📰 Анализ другой статьи", callback_data="analyze_article")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                "**Что дальше?**",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при Deep Research: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка при проведении Deep Research. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
    
    def run(self):
        """Запуск бота"""
        logger.info("Запуск Telegram-бота...")
        
        try:
            # Сначала удаляем возможный webhook, чтобы исключить конфликт с polling
            try:
                import asyncio as _asyncio
                _asyncio.run(self.application.bot.delete_webhook(drop_pending_updates=True))
                logger.info("Webhook удален (drop_pending_updates=True)")
            except Exception as e_w:
                logger.warning(f"Не удалось удалить webhook: {e_w}")

            # Запускаем бота с очисткой подвисших апдейтов, чтобы избежать 409 Conflict
            self.application.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise

def main():
    """Главная функция"""
    try:
        bot = TelegramFactCheckerBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
