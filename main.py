#!/usr/bin/env python3
"""
Telegram-бот для проверки фактов и анализа статей
Две основные функции:
1. Анализ статей с помощью Perplexity API
2. Проверка утверждений
"""

import asyncio
import re
import logging
import os
import sys
from datetime import datetime
from typing import Optional
from collections import defaultdict

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
from services.professional_factchecker_service import ProfessionalFactCheckerService
from services.message_delivery_service import MessageDeliveryService
from services.professional_editor_service import ProfessionalEditorService
from utils.logger import setup_logger
from utils.professional_response_formatter import ProfessionalResponseFormatter
from storage.ratelimit import rate_limiter
from storage.jobs import JobStorage
from worker import start_worker_background

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
        
        # Новые сервисы версии 2.0
        self.professional_factchecker = ProfessionalFactCheckerService(self.config.PERPLEXITY_API_KEY)
        self.message_delivery = MessageDeliveryService()
        self.professional_formatter = ProfessionalResponseFormatter()
        self.professional_editor = ProfessionalEditorService(self.config.PERPLEXITY_API_KEY)
        # Ограничение параллельных задач на пользователя
        self._active_tasks = defaultdict(int)  # user_id -> count
        
        # Создаем приложение с конкурентной обработкой апдейтов
        self.application = (
            Application.builder()
            .token(self.config.TELEGRAM_TOKEN)
            .concurrent_updates(True)
            .post_init(self._post_init)
            .build()
        )
        
        # Регистрируем обработчики
        self._register_handlers()
    
    def _register_handlers(self):
        """Регистрация обработчиков команд и сообщений"""
        # Команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("menu", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("promo", self.promo_command))
        self.application.add_handler(CommandHandler("health", self.health_command))
        self.application.add_handler(CommandHandler("analyze_long", self.analyze_long_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel_command))
        
        # Обработчики сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработчики callback-запросов
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

    async def _post_init(self, app: Application) -> None:
        """Запуск фонового воркера для длинных задач (IFCN) после старта приложения."""
        try:
            await start_worker_background()
            logger.info("Фоновый воркер запущен")
        except Exception as e:
            logger.error(f"Не удалось запустить воркер: {e}")
    
    async def send_or_edit_message(self, query_or_update, text: str, reply_markup=None, parse_mode='Markdown'):
        """Универсальный метод для отправки или редактирования сообщения"""
        if hasattr(query_or_update, 'edit_message_text'):
            # Это CallbackQuery - редактируем сообщение
            await query_or_update.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            # Это Update - отправляем новое сообщение
            await query_or_update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

    async def send_or_update_menu(self, update_or_query, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode='Markdown'):
        """Показывает меню, гарантируя, что виден ОДИН экземпляр (редактируем существующее, а не создаем новое)."""
        try:
            if hasattr(update_or_query, 'edit_message_text'):
                # CallbackQuery: редактируем сообщение с кнопками
                msg = await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
                # Сохраняем id меню
                try:
                    context.user_data['last_menu_message_id'] = (msg.message_id if hasattr(msg, 'message_id') else update_or_query.message.message_id)
                except Exception:
                    pass
                return
            # Иначе это Update
            chat_id = update_or_query.effective_chat.id
            last_id = context.user_data.get('last_menu_message_id')
            if last_id:
                # Пробуем отредактировать предыдущее меню
                try:
                    await self.application.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=last_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
                    return
                except Exception:
                    pass
            # Если нечего редактировать — отправляем новое и запоминаем id
            sent = await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            try:
                context.user_data['last_menu_message_id'] = sent.message_id
            except Exception:
                pass
        except Exception as _:
            # Fallback на обычную отправку
            await self.send_or_edit_message(update_or_query, text, reply_markup, parse_mode)
        
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
🔍 **Добро пожаловать в FactChecker Bot 2.0!**

Привет, {username}! Я профессиональный факт-чекер с улучшенными возможностями.

**🆕 Что нового в версии 2.0:**
• Профессиональные стандарты фактчекинга
• Многоуровневый анализ источников
• Полные ответы без обрезания
• Улучшенная структура и читаемость

**📊 Ваша статистика:**
• Сегодня: {user_stats['daily_requests']}/{user_stats['daily_limit']}
• Всего: {user_stats['total_requests']}
• Баланс: {user_stats['balance']} запросов

**Выберите действие:**
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📰 Анализ статьи", callback_data="analyze_article"),
                InlineKeyboardButton("🔍 Проверка факта", callback_data="check_fact")
            ],
            [
                InlineKeyboardButton("🔬 Deep Research", callback_data="deep_research"),
                InlineKeyboardButton("📊 Мои запросы", callback_data="user_stats")
            ],
            [
                InlineKeyboardButton("💳 Купить запросы", callback_data="buy_requests"),
                InlineKeyboardButton("❓ Помощь", callback_data="help")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Для команды /start: показываем меню НИЖЕ последнего сообщения
        # Удаляем предыдущее меню (если было), затем отправляем НОВОЕ сообщение
        try:
            last_id = context.user_data.get('last_menu_message_id')
            if last_id:
                try:
                    await self.application.bot.delete_message(chat_id=update.effective_chat.id, message_id=last_id)
                except Exception:
                    pass
            sent = await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
            context.user_data['last_menu_message_id'] = sent.message_id
        except Exception:
            # Фоллбэк на прежнюю логику
            await self.send_or_update_menu(update, context, welcome_text, reply_markup, 'Markdown')
        # Установим меню команд, чтобы не листать историю
        try:
            await self.application.bot.set_my_commands([
                ("start", "Главное меню"),
                ("menu", "Открыть меню"),
                ("help", "Помощь"),
                ("analyze_long", "Длинный анализ (IFCN)"),
                ("status", "Статус задачи"),
                ("cancel", "Отмена задачи"),
            ])
        except Exception:
            pass
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🔍 Помощь

Что умеет бот:
• Анализ статьи по ссылке или тексту: краткий вывод, факт-чекинг и источники
• Проверка конкретного утверждения: вердикт, доказательства и источники

Как это работает:
• Мы используем ИИ и проверку источников (с приоритетом академических и официальных)
• Ссылки проверяются на доступность и качество, слабые источники помечаются

Команды:
/start — главное меню
/help — справка

Ограничения:
• Бесплатно: 3 запроса в день
• Платные пакеты: без дневных ограничений
        """

        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Быстрая диагностика бота"""
        try:
            # Проверка конфигурации
            ok_cfg = bool(self.config.TELEGRAM_TOKEN and self.config.PERPLEXITY_API_KEY)
            # Проверка базовых сервисов
            ok_services = all([
                self.professional_factchecker is not None,
                self.message_delivery is not None,
                self.professional_formatter is not None,
            ])
            # Пинг Telegram API
            me = await self.application.bot.get_me()
            ok_tg = bool(me and me.username)
            status_lines = [
                "🩺 Healthcheck:",
                f"• Config: {'OK' if ok_cfg else 'FAIL'}",
                f"• Services: {'OK' if ok_services else 'FAIL'}",
                f"• Telegram API: {'OK' if ok_tg else 'FAIL'} (@{me.username if ok_tg else ''})",
            ]
            await update.message.reply_text("\n".join(status_lines))
        except Exception as e:
            await update.message.reply_text(f"❌ Healthcheck error: {e}")

    async def analyze_long_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Создать задачу длинного IFCN-анализа"""
        user_id = update.effective_user.id
        args = context.args if hasattr(context, 'args') else []
        text = " ".join(args).strip() or (update.message.text or "").replace("/analyze_long", "", 1).strip()
        if not text:
            await update.message.reply_text("Использование: /analyze_long <утверждение или URL>")
            return
        jobs = JobStorage()
        await jobs.init()
        job_id = await jobs.create_job(user_id, "ifcn_long", {"input": text})
        await update.message.reply_text(f"✅ Задача создана: job_id={job_id}\nПроверяйте статус: /status {job_id}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статус задачи"""
        args = context.args if hasattr(context, 'args') else []
        if not args:
            await update.message.reply_text("Использование: /status <job_id>")
            return
        try:
            job_id = int(args[0])
        except Exception:
            await update.message.reply_text("Некорректный job_id")
            return
        jobs = JobStorage()
        await jobs.init()
        job = await jobs.get_job(job_id)
        if not job:
            await update.message.reply_text("Задача не найдена")
            return
        log_tail = job.log[-1500:] if job.log else ""
        await update.message.reply_text(
            f"job_id={job.id}\nstatus={job.status}\nprogress={int((job.progress or 0)*100)}%\n---\n{log_tail}"
        )

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отменить задачу"""
        args = context.args if hasattr(context, 'args') else []
        if not args:
            await update.message.reply_text("Использование: /cancel <job_id>")
            return
        try:
            job_id = int(args[0])
        except Exception:
            await update.message.reply_text("Некорректный job_id")
            return
        jobs = JobStorage()
        await jobs.init()
        await jobs.update_status(job_id, "canceled")
        await update.message.reply_text(f"🛑 Задача отменена: {job_id}")
    
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
        
        keyboard = [
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"), InlineKeyboardButton("📰 Анализ статьи", callback_data="analyze_article")],
            [InlineKeyboardButton("🔍 Проверка факта", callback_data="check_fact"), InlineKeyboardButton("🔬 Deep Research", callback_data="deep_research")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
            
        # Отправляем сообщение в зависимости от типа объекта
        if hasattr(update_or_query, 'message'):
            # Это Update
            await update_or_query.message.reply_text(
                "🔑 Введите код",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Это CallbackQuery
            await update_or_query.message.reply_text(
                "🔑 Введите код",
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
            
            # Если ожидается подтверждение Deep Research — не переключаемся на проверку факта
            if context.user_data.get('awaiting_confirm_deep_research'):
                await update.message.reply_text(
                    "🔬 Ожидается подтверждение Deep Research.\n\n"
                    "Пожалуйста, нажмите кнопку \"✅ Подтвердить\" под предыдущим сообщением, чтобы запустить исследование.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]),
                    parse_mode='Markdown'
                )
                return
            # Проверяем режим работы
            mode = context.user_data.get('mode')
        
            if mode == 'analyze_article':
                await self.handle_article_analysis(update, context)
            elif mode == 'check_fact':
                await self.handle_fact_check(update, context)
            elif mode == 'deep_research_input':
                # Пользователь ввёл тему для Deep Research
                topic_text = message_text.strip()
                context.user_data['last_topic'] = topic_text
                context.user_data['last_analysis'] = (
                    f"Исходные данные от пользователя.\n"
                    f"Тема: {topic_text}. Проведи углублённое исследование по этой теме, \n"
                    f"найди дополнительные независимые источники на ЛЮБОМ языке, статистику и экспертные мнения."
                )
                # Сбрасываем режим ввода
                context.user_data['mode'] = None

                # Предложим подтверждение Deep Research
                user_id = update.effective_user.id
                is_free = self.user_service.can_use_deep_research(user_id)
                cost_text = "БЕСПЛАТНО" if is_free else "449 запросов"
                button_text = "✅ Подтвердить (БЕСПЛАТНО)" if is_free else "✅ Подтвердить (449₽)"
                keyboard = [
                    [InlineKeyboardButton(button_text, callback_data="confirm_deep_research")],
                    [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                context.user_data['awaiting_confirm_deep_research'] = True
                await update.message.reply_text(
                    "🔬 **Deep Research**\n\n"
                    "Глубокое исследование темы с расширенным анализом.\n\n"
                    f"**Стоимость: {cost_text}**\n\n"
                    "Нажмите подтверждение, чтобы начать.",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            elif re.search(r'(https?://)?[\w.-]+\.[a-zA-Z]{2,}(/\S*)?', message_text):
                # Обнаружена ссылка (в т.ч. без схемы) — нормализуем и запускаем анализ статьи
                if not re.search(r'https?://', message_text):
                    try:
                        update.message.text = 'https://' + message_text.strip()
                    except Exception:
                        pass
                await self.handle_article_analysis(update, context)
            else:
                # Автоматически предлагаем и запускаем проверку факта для любого текста
                await self.handle_fact_check(update, context)
                
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
        """Обработка анализа статьи (версия 2.0)"""
        user_id = update.effective_user.id
        message_text = update.message.text
        # Ограничение параллельных задач: free=1, paid=2
        if not self._try_acquire_slot(user_id):
            limit, used, is_paid = self._current_limit_state(user_id)
            await self._show_concurrency_block(update, limit, used, is_paid, task_name="Анализ статьи")
            return
        
        # Проверяем суточный лимит (in-memory) и дневной лимит UserService
        allowed, remaining = await rate_limiter.check_and_increment(user_id)
        if not allowed or not self.user_service.check_daily_limit(user_id):
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
            # Показываем индикатор загрузки с прогрессом
            loading_message = await update.message.reply_text(
                "🔍 **Запускаю профессиональный анализ статьи...**\n\n"
                "⏱️ Ожидаемое время: 2-3 минуты\n"
                "🔬 Применяю стандарты профессионального фактчекинга\n\n"
                "⏳ Пожалуйста, подождите..."
            )
            
            logger.info(f"Начинаем профессиональный анализ для пользователя {user_id}: {message_text[:100]}...")
            
            # Проводим профессиональный анализ статьи
            if message_text.startswith('http'):
                # Это ссылка - используем новый профессиональный сервис
                logger.info(f"Анализируем ссылку профессиональным методом: '{message_text}'")
                analysis_result = await self.professional_factchecker.analyze_article_professionally(message_text)
                logger.info(f"Профессиональный анализ завершен")
            else:
                # Это текст - используем старый метод для совместимости
                logger.info("Анализируем текст через стандартный API...")
                analysis = await self.perplexity_service.analyze_text(message_text)
                # Конвертируем в новый формат
                from datetime import datetime
                analysis_result = {
                    "url": "Текстовый ввод",
                    "timestamp": datetime.now().isoformat(),
                    "final_assessment": {"assessment": analysis},
                    "overall_rating": "⚪ ТРЕБУЕТ ДОПОЛНИТЕЛЬНОЙ ПРОВЕРКИ",
                    "recommendations": ["Проверьте информацию по дополнительным источникам"]
                }
                logger.info(f"Анализ завершен, результат: {str(analysis)[:200]}...")
            
            # Учитываем запрос
            self.user_service.make_request(user_id)
            
            # Удаляем сообщение о загрузке
            await loading_message.delete()
            
            # Сохраняем контекст для Deep Research
            context.user_data['last_topic'] = message_text
            context.user_data['last_analysis'] = analysis_result
            
            # Форматируем ответ: 2 сообщения
            formatted_messages = self.professional_formatter.format_professional_article_analysis(analysis_result)
            
            # Валидируем только второй блок (источники) и обеспечиваем минимум 5
            from services.source_validator_service import SourceValidatorService
            validator = SourceValidatorService()
            validated_messages = formatted_messages[:]
            if len(validated_messages) >= 2:
                validated_messages[1] = await validator.build_verified_sources_block(
                    validated_messages[1],
                    min_required=5,
                    title="📚 Источники (статья)",
                    exclude_categories=["blog_social"],
                    exclude_domains=["wikipedia.org"],
                    limit=12,
                )

            # Лёгкая редакттура первых блоков (ответ/почему/что делать)
            for i in range(min(3, len(validated_messages))):
                validated_messages[i] = await self.professional_editor.polish_text(validated_messages[i])

            # Отправляем структурированный ответ без навигации/меню
            await self.message_delivery.send_structured_response(update, context, validated_messages, show_progress=False, add_navigation=False)

            # Предложение Deep Research одной кнопкой
            try:
                keyboard = [[InlineKeyboardButton("🔬 Глубокое исследование", callback_data="confirm_deep_research")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "🔬 Запустить Глубокое исследование?",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except Exception:
                pass
            
        except Exception as e:
            logger.error(f"Ошибка при анализе статьи: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при анализе статьи. Попробуйте еще раз.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
        finally:
            self._release_slot(user_id)
    
    async def handle_fact_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка проверки факта (версия 2.0)"""
        user_id = update.effective_user.id
        message_text = update.message.text
        # Ограничение параллельных задач: free=1, paid=2
        if not self._try_acquire_slot(user_id):
            limit, used, is_paid = self._current_limit_state(user_id)
            await self._show_concurrency_block(update, limit, used, is_paid, task_name="Проверка факта")
            return
        
        # Проверяем суточный лимит (in-memory) и дневной лимит UserService
        allowed, remaining = await rate_limiter.check_and_increment(user_id)
        if not allowed or not self.user_service.check_daily_limit(user_id):
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
            # Показываем индикатор загрузки с прогрессом
            loading_message = await update.message.reply_text(
                "🔍 **Запускаю профессиональную проверку факта...**\n\n"
                "⏱️ Ожидаемое время: 2-3 минуты\n"
                "🔬 Применяю многоуровневый анализ\n"
                "📚 Проверяю по множественным источникам\n\n"
                "⏳ Пожалуйста, подождите..."
            )
            
            logger.info(f"Начинаем профессиональную проверку факта для пользователя {user_id}: {message_text[:100]}...")
            
            # Проводим профессиональную проверку факта
            factcheck_result = await self.professional_factchecker.conduct_professional_factcheck(message_text)
            
            # Учитываем запрос
            self.user_service.make_request(user_id)
            
            # Удаляем сообщение о загрузке
            await loading_message.delete()
            
            # Сохраняем контекст для Deep Research
            context.user_data['last_topic'] = f"Факт-чек утверждения: {message_text[:200]}"
            context.user_data['last_analysis'] = factcheck_result
            
            # Форматируем ответ: 2 сообщения
            formatted_messages = self.professional_formatter.format_professional_factcheck(factcheck_result)
            
            # Валидируем только второй блок (источники) и обеспечиваем минимум 5 академических источников
            from services.source_validator_service import SourceValidatorService
            validator = SourceValidatorService()
            validated_messages = formatted_messages[:]
            if len(validated_messages) >= 2:
                # Сначала проверяем, есть ли достаточно академических источников
                sources_text = validated_messages[1]
                sources = validator.extract_sources_from_text(sources_text)
                academic_count = validator.count_academic_sources(sources)
                
                if academic_count < 5:
                    # Если академических источников недостаточно, добавляем предупреждение
                    validated_messages[1] = sources_text + f"\n\n⚠️ **Внимание**: Найдено только {academic_count} академических источников. Для качественной проверки фактов рекомендуется минимум 5 академических источников или whitepaper."
                
                validated_messages[1] = await validator.build_verified_sources_block(
                    validated_messages[1],
                    min_required=5,
                    title="📚 Источники (факт)",
                    exclude_categories=["blog_social"],
                    exclude_domains=["wikipedia.org"],
                    limit=15,  # Увеличиваем лимит для поиска больше академических источников
                )

            # Лёгкая редакттура первых блоков (ответ/почему/что делать)
            for i in range(min(3, len(validated_messages))):
                validated_messages[i] = await self.professional_editor.polish_text(validated_messages[i])

            # Отправляем структурированный ответ без навигации/меню
            await self.message_delivery.send_structured_response(update, context, validated_messages, show_progress=False, add_navigation=False)

            # Предложение Deep Research одной кнопкой
            try:
                keyboard = [[InlineKeyboardButton("🔬 Глубокое исследование", callback_data="confirm_deep_research")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "🔬 Запустить Глубокое исследование?",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except Exception:
                pass
            
        except Exception as e:
            logger.error(f"Ошибка при проверке факта: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при проверке факта. Попробуйте еще раз.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
        finally:
            self._release_slot(user_id)
    
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
        elif data == "noop":
            # Ничего не делаем, просто закрываем всплывашку
            try:
                await query.answer()
            except Exception:
                pass
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
            "📰 **Профессиональный анализ статьи (v2.0)**\n\n"
            "Отправьте ссылку на статью или скопируйте текст для анализа.\n\n"
            "🔬 **Многоуровневый анализ:**\n"
            "• Детальная проверка содержания\n"
            "• Верификация всех фактов по независимым источникам\n"
            "• Оценка качества и надежности источников\n"
            "• Итоговая оценка достоверности статьи\n"
            "• Профессиональные рекомендации\n\n"
            "⏱️ Время анализа: 2-3 минуты",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def start_fact_check(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Начать проверку факта"""
        context.user_data['mode'] = 'check_fact'
        
        keyboard = [
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"), InlineKeyboardButton("📰 Анализ статьи", callback_data="analyze_article")],
            [InlineKeyboardButton("🔍 Проверка факта", callback_data="check_fact"), InlineKeyboardButton("🔬 Deep Research", callback_data="deep_research")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
            
        await query.edit_message_text(
            "🔍 **Профессиональная проверка факта (v2.0)**\n\n"
            "Напишите утверждение для проверки.\n\n"
            "🔬 **Многоуровневая проверка:**\n"
            "• Первичный анализ и структурирование\n"
            "• Глубокое исследование источников\n"
            "• Критический анализ и верификация\n"
            "• Формирование финального заключения\n"
            "• Оценка уровня уверенности\n\n"
            "⏱️ Время проверки: 2-3 минуты",
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
        
        keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"), InlineKeyboardButton("🔑 Ввести код", callback_data="promo_code")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_payment_options(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Показать варианты поддержки/оплаты"""
        prices = {
            # Обычные запросы
            "buy_10": {"price": 100, "requests": 10, "label": "10 запросов"},
            "buy_50": {"price": 400, "requests": 50, "label": "50 запросов"},
            "buy_100": {"price": 700, "requests": 100, "label": "100 запросов"},
            "buy_500": {"price": 3000, "requests": 500, "label": "500 запросов"},
            # Deep Research кредиты
            "buy_dr_1": {"price": 149, "dr": 1, "label": "1 Глубокое исследование"},
            "buy_dr_3": {"price": 449, "dr": 3, "label": "3 Глубоких исследования"},
            "buy_dr_12": {"price": 1490, "dr": 12, "label": "12 Глубоких исследований"},
        }
        
        keyboard = []
        # Блок обычных запросов
        keyboard.append([InlineKeyboardButton("🧰 Пакеты запросов", callback_data="noop")])
        for key in ["buy_10", "buy_50", "buy_100", "buy_500"]:
            value = prices[key]
            keyboard.append([
                InlineKeyboardButton(
                    f"💳 {value['label']} — {value['price']}₽",
                    callback_data=key
                )
            ])
        # Блок Deep Research
        keyboard.append([InlineKeyboardButton("🔬 Глубокое исследование (кредиты)", callback_data="noop")])
        for key in ["buy_dr_1", "buy_dr_3", "buy_dr_12"]:
            value = prices[key]
            keyboard.append([
                InlineKeyboardButton(
                    f"🔬 {value['label']} — {value['price']}₽",
                    callback_data=key
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🤝 **Поддержите миссию — получите больше ясности**\n\n"
            "Ваш взнос помогает делать мир честнее. В ответ — доступ к глубоким исследованиям и больше проверок.\n\n"
            "Выберите вариант:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_payment_selection(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        """Обработка выбора пакета/кредита"""
        prices = {
            # Обычные запросы
            "buy_10": {"price": 100, "requests": 10, "label": "10 запросов"},
            "buy_50": {"price": 400, "requests": 50, "label": "50 запросов"},
            "buy_100": {"price": 700, "requests": 100, "label": "100 запросов"},
            "buy_500": {"price": 3000, "requests": 500, "label": "500 запросов"},
            # Deep Research кредиты
            "buy_dr_1": {"price": 149, "dr": 1, "label": "1 Глубокое исследование"},
            "buy_dr_3": {"price": 449, "dr": 3, "label": "3 Глубоких исследования"},
            "buy_dr_12": {"price": 1490, "dr": 12, "label": "12 Глубоких исследований"},
        }
        
        if data not in prices or data == "noop":
            await query.edit_message_text("❌ Неверный пакет запросов")
            return
        
        user_id = query.from_user.id
        price_info = prices[data]
        
        try:
            # Создаем платеж
            payment = await self.payment_service.create_payment(
                user_id=user_id,
                amount=price_info['price'],
                description=f"Покупка: {price_info.get('label','пакет')}"
            )
            
            if payment:
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
        
                # Так как платеж у нас заглушка, сразу начислим и покажем подтверждение
                if 'requests' in price_info:
                    self.user_service.add_requests(user_id, price_info['requests'])
                    credited_text = f"Начислено: {price_info['requests']} запросов"
                else:
                    self.user_service.add_deep_research_credits(user_id, price_info['dr'])
                    credited_text = f"Начислено: {price_info['dr']} Deep Research"

                await query.edit_message_text(
                    f"✅ **Оплата оформлена**\n\n"
                    f"{price_info.get('label','Пакет')} — {price_info['price']}₽\n"
                    f"{credited_text}\n\n"
                    f"Спасибо за поддержку миссии!",
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
        # Поддерживаем как Update, так и CallbackQuery
        if hasattr(query, 'effective_user'):
            user_id = query.effective_user.id
            username = query.effective_user.username or "Пользователь"
        else:
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
            [
                InlineKeyboardButton("📰 Анализ статьи", callback_data="analyze_article"),
                InlineKeyboardButton("🔍 Проверка факта", callback_data="check_fact")
            ],
            [
                InlineKeyboardButton("🔬 Deep Research", callback_data="deep_research"),
                InlineKeyboardButton("📊 Мои запросы", callback_data="user_stats")
            ],
            [
                InlineKeyboardButton("💳 Купить запросы", callback_data="buy_requests"),
                InlineKeyboardButton("❓ Помощь", callback_data="help")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Гарантируем единичный экземпляр меню
        await self.send_or_update_menu(query, context, welcome_text, reply_markup, 'Markdown')
    
    async def handle_deep_research(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Обработка запроса на Deep Research"""
        user_id = query.from_user.id
        
        # Логируем имеющийся контекст
        try:
            logger.info(f"Deep Research user_data keys: {list(context.user_data.keys())}")
        except Exception:
            pass
        
        # Проверяем, есть ли контекст для Deep Research
        if not context.user_data.get('last_analysis') and not context.user_data.get('last_topic'):
            # Переводим в режим ввода темы для Deep Research
            context.user_data['mode'] = 'deep_research_input'
            keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🔬 **Deep Research**\n\n"
                "Опишите тему или пришлите ссылку для углублённого исследования.\n\n"
                "Источники могут быть на ЛЮБОМ языке, ответ будет на русском.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        elif not context.user_data.get('last_analysis') and context.user_data.get('last_topic'):
            fallback_topic = context.user_data.get('last_topic')
            context.user_data['last_analysis'] = (
                f"Исходные данные получены из последнего действия пользователя.\n"
                f"Тема: {fallback_topic}. Проведи углублённое исследование по этой теме, \n"
                f"найди дополнительные независимые источники на ЛЮБОМ языке, статистику и экспертные мнения."
            )
        
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
        
        # Показываем подтверждение
        is_free = self.user_service.can_use_deep_research(user_id)
        cost_text = "БЕСПЛАТНО" if is_free else "449 запросов"
        button_text = "✅ Подтвердить (БЕСПЛАТНО)" if is_free else "✅ Подтвердить (449₽)"
        
        keyboard = [
            [InlineKeyboardButton(button_text, callback_data="confirm_deep_research")],
            [InlineKeyboardButton("📰 Анализ статьи", callback_data="analyze_article"), InlineKeyboardButton("🔍 Проверка факта", callback_data="check_fact")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
                
        context.user_data['awaiting_confirm_deep_research'] = True
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
            # Сбрасываем ожидание подтверждения
            context.user_data['awaiting_confirm_deep_research'] = False
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
            topic = context.user_data.get('last_topic') or "Тема не указана"
            initial_analysis_raw = context.user_data.get('last_analysis')
            # Преобразуем контекст анализа в строку для передачи в модель
            if isinstance(initial_analysis_raw, dict):
                import json as _json
                initial_analysis = _json.dumps(initial_analysis_raw, ensure_ascii=False)
            else:
                initial_analysis = str(initial_analysis_raw or "")
            
            logger.info(f"Начинаем Deep Research для пользователя {user_id}")
            logger.info(f"Тема: {topic}")
            try:
                logger.info(f"Начальный анализ: {initial_analysis[:200]}...")
            except Exception:
                logger.info("Начальный анализ: [недоступен для логирования]")
            
            import time
            start_time = time.time()
            
            try:
                # Создаем задачу для Deep Research
                deep_research_task = asyncio.create_task(
                    self.deep_research_service.conduct_deep_research(topic, initial_analysis)
                )
                
                # Промежуточные обновления статуса
                status_messages = [
                    "🔍 Ищу независимые источники...",
                    "📊 Анализирую экспертные мнения...",
                    "📈 Собираю статистические данные...",
                    "🌍 Проверяю международные источники...",
                    "⚖️ Ищу альтернативные точки зрения...",
                    "🎯 Формирую заключение..."
                ]
                
                # Показать первый шаг сразу
                message_index = 0
                await query.edit_message_text(
                    f"🔬 Глубокое Исследование...\n\n"
                    f"⏱️ Прошло: {int(time.time() - start_time)} секунд\n"
                    f"📊 {status_messages[message_index]}\n\n"
                    f"⏳ Пожалуйста, подождите..."
                )
                message_index += 1

                # Далее обновлять чаще, каждые ~10 сек, циклически по списку
                while not deep_research_task.done():
                    await asyncio.sleep(10)
                    if not deep_research_task.done():
                        current_status = status_messages[message_index % len(status_messages)]
                        await query.edit_message_text(
                            f"🔬 Глубокое Исследование...\n\n"
                            f"⏱️ Прошло: {int(time.time() - start_time)} секунд\n"
                            f"📊 {current_status}\n\n"
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
            
            # Формируем компактную выдачу: 2 сообщения (вывод + источники)
            from utils.response_formatter import ResponseFormatter
            formatter = ResponseFormatter()
            messages = formatter.build_deep_research_messages(deep_research_result)

            # Валидируем только второй блок (источники) и требуем ≥5
            from services.source_validator_service import SourceValidatorService
            _validator = SourceValidatorService()
            if len(messages) >= 2:
                messages[1] = await _validator.build_verified_sources_block(
                    messages[1],
                    min_required=5,
                    title="📚 Источники (Deep Research)",
                    exclude_categories=["blog_social"],
                    exclude_domains=["wikipedia.org"],
                    limit=20,
                )

            # Отправляем без прогресса/навигации
            await self.message_delivery.send_structured_response(
                query,
                context,
                messages,
                show_progress=False,
                add_navigation=False,
            )
    
            # После Deep Research ничего не добавляем (без меню)
            
        except Exception as e:
            logger.error(f"Ошибка при Deep Research: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка при проведении Deep Research. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
    
    def run(self):
        """Запуск бота (Webhook или Polling)"""
        logger.info("Запуск Telegram-бота...")
        
        try:
            # Определяем режим
            base = os.getenv("WEBHOOK_URL", "").strip() or self.config.WEBHOOK_BASE_URL
            path = self.config.WEBHOOK_PATH or os.getenv("WEBHOOK_PATH", f"/{self.config.TELEGRAM_TOKEN}")
            port = int(os.getenv("PORT", "8000"))

            if base and path:
                # Запуск в режиме webhook
                webhook_full = base.rstrip("/") + (path if path.startswith("/") else "/" + path)
                logger.info(f"Включаем Webhook: url={webhook_full}, listen=0.0.0.0:{port}")
                import asyncio as _asyncio
                _asyncio.run(self.application.bot.set_webhook(url=webhook_full, drop_pending_updates=True))

                # aiohttp web приложение с /healthz
                from aiohttp import web as _web

                async def _healthz(_request):
                    return _web.Response(text="ok")

                app = _web.Application()
                app.router.add_get("/healthz", _healthz)
                app.router.add_get("/health", _healthz)

                self.application.run_webhook(
                    listen="0.0.0.0",
                    port=port,
                    url_path=path,
                    web_app=app,
                )
            else:
                # Fallback: polling (локально)
                logger.info("WEBHOOK_URL не задан — запускаем polling")
                # Удаляем webhook, если он был установлен ранее, чтобы избежать конфликтов
                try:
                    import asyncio as _asyncio
                    # удалено для стабильного polling
                except Exception as e:
                    logger.warning(f"Не удалось удалить старый webhook: {e}")
                # Запускаем polling
                self.application.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise

    # === Ограничение параллельных задач ===
    def _is_paid_user(self, user_id: int) -> bool:
        stats = self.user_service.get_user_stats(user_id)
        return (stats.get("balance", 0) > 0) or (stats.get("deep_research_credits", 0) > 0)

    def _get_limit(self, user_id: int) -> int:
        return 2 if self._is_paid_user(user_id) else 1

    def _try_acquire_slot(self, user_id: int) -> bool:
        limit = self._get_limit(user_id)
        used = self._active_tasks[user_id]
        if used >= limit:
            return False
        self._active_tasks[user_id] = used + 1
        return True

    def _release_slot(self, user_id: int) -> None:
        used = self._active_tasks.get(user_id, 0)
        if used <= 1:
            self._active_tasks.pop(user_id, None)
        else:
            self._active_tasks[user_id] = used - 1

    def _current_limit_state(self, user_id: int):
        limit = self._get_limit(user_id)
        used = self._active_tasks.get(user_id, 0)
        return limit, used, self._is_paid_user(user_id)

    async def _show_concurrency_block(self, update_or_query, limit: int, used: int, is_paid: bool, task_name: str):
        tariff = "ПЛАТНЫЙ (2 параллельно)" if is_paid else "БЕСПЛАТНЫЙ (1 параллельно)"
        text = (
            "⛔ **Лимит одновременных проверок**\n\n"
            f"Ваш тариф: {tariff}.\n"
            f"Сейчас уже выполняется: {used}/{limit}.\n\n"
            f"Дождитесь завершения текущих задач и запустите «{task_name}» снова."
        )
        keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            if hasattr(update_or_query, 'message') and update_or_query.message:
                await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception:
            pass

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
