from django.contrib import admin
from django.utils.html import format_html
from .models import DiaryEntry, ExtractedKeyword, MoodCorrelation


@admin.register(DiaryEntry)
class DiaryEntryAdmin(admin.ModelAdmin):
    """Административный интерфейс для дневниковых записей"""

    list_display = (
        'user',
        'short_text_preview',
        'date_created',
        'user_mood_tag',
        'mood_score_display',
        'word_count'
    )

    list_filter = (
        'user_mood_tag',
        'date_created',
        'user',
    )

    search_fields = (
        'text',
        'user__username',
        'user__email',
    )

    readonly_fields = (
        'mood_score',
        'word_count',
        'date_created',
    )

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'date_created')
        }),
        ('Содержание', {
            'fields': ('text', 'user_mood_tag')
        }),
        ('Автоматический анализ', {
            'fields': ('mood_score', 'word_count'),
            'classes': ('collapse',)  # Сворачиваемый блок
        }),
    )

    def short_text_preview(self, obj):
        """Короткий превью текста записи"""
        if len(obj.text) > 50:
            return f"{obj.text[:50]}..."
        return obj.text

    short_text_preview.short_description = 'Текст (превью)'

    def mood_score_display(self, obj):
        """Цветное отображение оценки настроения"""
        if obj.mood_score is None:
            return "Не анализировано"

        # Определяем цвет в зависимости от оценки
        if obj.mood_score > 0.3:
            color = 'green'
            emoji = '😊'
        elif obj.mood_score > 0:
            color = 'lightgreen'
            emoji = '🙂'
        elif obj.mood_score > -0.3:
            color = 'orange'
            emoji = '😐'
        else:
            color = 'red'
            emoji = '😔'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {:.2f}</span>',
            color, emoji, obj.mood_score
        )

    mood_score_display.short_description = 'Оценка настроения'


@admin.register(ExtractedKeyword)
class ExtractedKeywordAdmin(admin.ModelAdmin):
    """Административный интерфейс для ключевых слов"""

    list_display = (
        'word',
        'category',
        'correlation_count',
    )

    list_filter = ('category',)

    search_fields = ('word',)

    def correlation_count(self, obj):
        """Количество корреляций для этого слова"""
        return MoodCorrelation.objects.filter(keyword=obj).count()

    correlation_count.short_description = 'Используется в корреляциях'


@admin.register(MoodCorrelation)
class MoodCorrelationAdmin(admin.ModelAdmin):
    """Административный интерфейс для корреляций настроения"""

    list_display = (
        'user',
        'keyword_with_category',
        'correlation_score_display',
        'occurrence_count',
        'last_updated',
        'correlation_label',
    )

    list_filter = (
        'user',
        'keyword__category',
    )

    search_fields = (
        'user__username',
        'keyword__word',
    )

    readonly_fields = ('last_updated',)

    ordering = ('-correlation_score',)

    def keyword_with_category(self, obj):
        """Отображение слова с его категорией"""
        return f"{obj.keyword.word} ({obj.keyword.get_category_display()})"

    keyword_with_category.short_description = 'Ключевое слово'

    def correlation_score_display(self, obj):
        """Цветное отображение коэффициента корреляции"""
        if obj.correlation_score > 0:
            color = 'green'
            sign = '+'
        elif obj.correlation_score < 0:
            color = 'red'
            sign = ''
        else:
            color = 'gray'
            sign = ''

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{:.3f}</span>',
            color, sign, obj.correlation_score
        )

    correlation_score_display.short_description = 'Коэффициент корреляции'

    def correlation_label(self, obj):
        """Текстовое описание корреляции"""
        return obj.get_correlation_label()

    correlation_label.short_description = 'Описание'


# Настраиваем заголовок админки
admin.site.site_header = "MoodPattern Tracker - Администрирование"
admin.site.site_title = "MoodPattern Tracker"
admin.site.index_title = "Панель управления"