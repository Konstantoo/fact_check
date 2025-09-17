class ResponseFormatter:
    def format_analysis(self, text: str) -> str:
        return text

    def format_fact_check(self, text: str) -> str:
        return text

    def format_deep_research(self, text: str) -> str:
        """Форматирует результат Deep Research для лучшей читаемости"""
        # Добавляем разделители для лучшей структуры
        formatted = text
        
        # Добавляем эмодзи для разделов
        formatted = formatted.replace("**ДЕТАЛЬНЫЙ АНАЛИЗ**", "📊 **ДЕТАЛЬНЫЙ АНАЛИЗ**")
        formatted = formatted.replace("**ЭКСПЕРТНЫЕ МНЕНИЯ**", "🔍 **ЭКСПЕРТНЫЕ МНЕНИЯ**")
        formatted = formatted.replace("**АВТОРИТЕТНЫЕ ИСТОЧНИКИ**", "📚 **АВТОРИТЕТНЫЕ ИСТОЧНИКИ**")
        formatted = formatted.replace("**СТАТИСТИКА И ДАННЫЕ**", "📈 **СТАТИСТИКА И ДАННЫЕ**")
        formatted = formatted.replace("**МНОГОСТОРОННИЙ ВЗГЛЯД**", "⚖️ **МНОГОСТОРОННИЙ ВЗГЛЯД**")
        formatted = formatted.replace("**ПРАКТИЧЕСКИЕ ВЫВОДЫ**", "🎯 **ПРАКТИЧЕСКИЕ ВЫВОДЫ**")
        
        return formatted
