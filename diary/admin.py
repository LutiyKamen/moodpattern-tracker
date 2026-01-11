from django.contrib import admin
from django.utils.safestring import mark_safe
from django import forms
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
        'text',  # Полнотекстовый поиск по содержанию
        'user__username',  # Поиск по имени пользователя
        'user__email',  # Поиск по email пользователя
        'user__first_name',  # Поиск по имени
        'user__last_name',  # Поиск по фамилии
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
            'classes': ('collapse',)
        }),
    )

    def get_search_results(self, request, queryset, search_term):
        """
        Расширенный поиск - ищет не только по указанным полям,
        но и может быть расширен для поиска по связанным объектам
        """
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )

        # Дополнительный поиск по корреляциям
        try:
            # Поиск записей, содержащих определенные ключевые слова
            if 'keyword:' in search_term:
                keyword = search_term.replace('keyword:', '').strip()
                from .models import ExtractedKeyword
                keyword_obj = ExtractedKeyword.objects.filter(word__icontains=keyword).first()
                if keyword_obj:
                    # Найти записи, содержащие это ключевое слово
                    queryset |= self.model.objects.filter(
                        text__icontains=keyword_obj.word
                    )
        except Exception:
            pass

        return queryset, use_distinct

    def short_text_preview(self, obj):
        """Короткий превью текста записи"""
        if obj.text:
            if len(obj.text) > 50:
                return f"{obj.text[:50]}..."
            return obj.text
        return "(пусто)"

    short_text_preview.short_description = 'Текст (превью)'

    def mood_score_display(self, obj):
        """Цветное отображение оценки настроения"""
        if obj.mood_score is None:
            return "Не анализировано"

        # Пороги для шкалы -10..10
        if obj.mood_score > 3:
            color = 'green'
            emoji = '😊'
        elif obj.mood_score > 0:
            color = 'lightgreen'
            emoji = '🙂'
        elif obj.mood_score > -3:
            color = 'orange'
            emoji = '😐'
        else:
            color = 'red'
            emoji = '😔'

        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{emoji} {obj.mood_score:.1f}</span>'
        )

    mood_score_display.short_description = 'Оценка настроения'


@admin.register(ExtractedKeyword)
class ExtractedKeywordAdmin(admin.ModelAdmin):
    """Административный интерфейс для ключевых слов"""

    list_display = (
        'word',
        'category',
        'correlation_count',
        'total_mentions',  # Новое поле
    )

    list_filter = ('category',)

    list_editable = ('category',)  # Теперь можно менять категорию прямо в таблице

    search_fields = ('word', 'category')

    # Добавляем actions для массовых операций
    actions = ['assign_work_category', 'assign_personal_category']

    # Поля, которые можно редактировать в форме
    fields = ('word', 'category', 'category_help_text')

    def get_form(self, request, obj=None, **kwargs):
        """Кастомизация формы с подсказками"""
        form = super().get_form(request, obj, **kwargs)

        # Добавляем help text для категории
        form.base_fields['category'].help_text = (
            'Выберите наиболее подходящую категорию для этого слова. '
            'Это повлияет на группировку в аналитике.'
        )

        # Добавляем поле с подсказкой (не сохраняется в БД)
        form.base_fields['category_help_text'] = forms.CharField(
            initial='Категории: работа, учеба, семья, друзья, здоровье, хобби, финансы, отдых, спорт, другое',
            widget=forms.TextInput(attrs={'readonly': 'readonly', 'style': 'border: none; background: transparent'}),
            required=False,
            label='Доступные категории'
        )

        return form

    def total_mentions(self, obj):
        """Общее количество упоминаний слова во всех записях"""
        from django.db.models import Sum
        from .models import MoodCorrelation
        return MoodCorrelation.objects.filter(keyword=obj).aggregate(
            total=Sum('occurrence_count')
        )['total'] or 0

    total_mentions.short_description = 'Всего упоминаний'
    total_mentions.admin_order_field = 'correlations__occurrence_count'

    def correlation_count(self, obj):
        """Количество корреляций для этого слова"""
        return MoodCorrelation.objects.filter(keyword=obj).count()

    correlation_count.short_description = 'Корреляций'

    # Action для массового назначения категории "Работа"
    def assign_work_category(self, request, queryset):
        updated = queryset.update(category='work')
        self.message_user(
            request,
            f'Категория "Работа" назначена {updated} ключевым словам.'
        )
    assign_work_category.short_description = 'Назначить категорию "Работа"'

    # Action для массового назначения категории "Личное"
    def assign_personal_category(self, request, queryset):
        updated = queryset.update(category='other')
        self.message_user(
            request,
            f'Категория "Другое" назначена {updated} ключевым словам.'
        )
    assign_personal_category.short_description = 'Назначить категорию "Другое"'

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
        if obj.correlation_score is None:
            return "Нет данных"

        if obj.correlation_score > 0:
            color = 'green'
            sign = '+'
        elif obj.correlation_score < 0:
            color = 'red'
            sign = ''
        else:
            color = 'gray'
            sign = ''

        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{sign}{obj.correlation_score:.3f}</span>'
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