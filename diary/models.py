from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .analysis_utils import analyze_text_sentiment, extract_keywords
from collections import Counter


class DiaryEntry(models.Model):
    """Модель для дневниковых записей пользователя"""

    # Выбор для субъективной оценки настроения
    MOOD_CHOICES = [
        ('excellent', 'Отличное'),
        ('good', 'Хорошее'),
        ('neutral', 'Нейтральное'),
        ('bad', 'Плохое'),
        ('terrible', 'Ужасное'),
    ]

    MOOD_VALUES = {
        'excellent': 10,
        'good': 5,
        'neutral': 0,
        'bad': -5,
        'terrible': -10,
    }

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='diary_entries',
        verbose_name='Пользователь'
    )
    text = models.TextField(
        verbose_name='Текст записи',
        help_text='Опишите свой день, мысли, события...'
    )
    date_created = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата создания'
    )
    mood_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-10.0), MaxValueValidator(10.0)],
        verbose_name='Оценка настроения (авто)',
        help_text='От -10 (очень негативное) до 10 (очень позитивное)'
    )
    user_mood_tag = models.CharField(
        max_length=20,
        choices=MOOD_CHOICES,
        default='neutral',
        verbose_name='Метка настроения'
    )
    # Новое поле для числовой оценки пользователя
    user_mood_value = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Оценка пользователя'
    )

    # Автоматически рассчитываемые поля (для аналитики)
    word_count = models.IntegerField(
        default=0,
        verbose_name='Количество слов'
    )

    class Meta:
        verbose_name = 'Дневниковая запись'
        verbose_name_plural = 'Дневниковые записи'
        ordering = ['-date_created']  # Новые записи сначала
        indexes = [
            models.Index(fields=['user', 'date_created']),
        ]

    def _update_correlation(self, word, mood_score, occurrence_increment=1):
        """Обновляет корреляцию для одного слова"""

        category = self._get_category_for_word(word)

        keyword, _ = ExtractedKeyword.objects.get_or_create(
            word=word,
            defaults={'category': category}
        )

        correlation, created = MoodCorrelation.objects.get_or_create(
            user=self.user,
            keyword=keyword,
            defaults={
                'correlation_score': mood_score,
                'occurrence_count': occurrence_increment
            }
        )

        if not created:
            total_occurrences = correlation.occurrence_count + occurrence_increment
            old_weight = correlation.occurrence_count / total_occurrences
            new_weight = occurrence_increment / total_occurrences

            new_correlation = (
                    correlation.correlation_score * old_weight +
                    mood_score * new_weight
            )

            # Ограничение -10..10
            new_correlation = max(-10.0, min(10.0, new_correlation))

            correlation.correlation_score = new_correlation
            correlation.occurrence_count = total_occurrences
            correlation.save()

    @staticmethod
    def _get_category_for_word(word):
        """Определяет категорию слова"""
        CATEGORY_KEYWORDS = {
            'work': ['работа', 'проект', 'задача', 'дедлайн'],
            'study': ['учеба', 'университет', 'экзамен', 'зачет'],
            'family': ['семья', 'родители', 'мама', 'папа'],
            'friends': ['друзья', 'друг', 'подруга', 'встреча'],
            'health': ['здоровье', 'болезнь', 'врач', 'боль'],
            'hobby': ['хобби', 'спорт', 'музыка', 'кино'],
            'finance': ['деньги', 'зарплата', 'покупка', 'траты'],
            'rest': ['отдых', 'отпуск', 'сон', 'релакс'],
        }

        for category, keywords in CATEGORY_KEYWORDS.items():
            if word in keywords:
                return category
        return 'other'

    def save(self, *args, **kwargs):
        """Автоматический анализ при сохранении записи"""

        # 1. Устанавливаем числовое значение настроения
        if self.user_mood_tag and not self.user_mood_value:
            self.user_mood_value = self.MOOD_VALUES.get(self.user_mood_tag, 0)

        # 2. Вычисляем количество слов
        self.word_count = len(self.text.split()) if self.text else 0

        # 3. Анализируем тональность текста
        if self.text and len(self.text.strip()) >= 10:
            try:
                self.mood_score = analyze_text_sentiment(
                    self.text,
                    self.user_mood_value
                )
            except Exception:
                self.mood_score = None

        # Сохраняем запись
        super().save(*args, **kwargs)

        # 4. Извлекаем ключевые слова и обновляем корреляции (после сохранения)
        if self.text and self.mood_score is not None:
            try:
                keywords = extract_keywords(self.text)
                word_counts = Counter(keywords)

                for word, count in word_counts.items():
                    if count >= 1:
                        # Используем существующую функцию из signals.py
                        # Или создаем новую в models.py
                        self._update_correlation(word, self.mood_score, count)

            except Exception as e:
                # Логируем ошибку, но не прерываем сохранение
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при анализе ключевых слов: {e}")

    def __str__(self):
        return f"{self.user.username} - {self.date_created.strftime('%d.%m.%Y')} - {self.get_user_mood_tag_display()}"

    def get_user_mood_numeric(self):
        """Возвращает числовое значение настроения пользователя"""
        return self.MOOD_VALUES.get(self.user_mood_tag, 0)

    def get_user_mood_tag_display(self):
        pass


class ExtractedKeyword(models.Model):
    """Модель для ключевых слов/тем, извлеченных из записей"""

    CATEGORY_CHOICES = [
        ('work', 'Работа'),
        ('study', 'Учёба'),
        ('family', 'Семья'),
        ('friends', 'Друзья'),
        ('health', 'Здоровье'),
        ('hobby', 'Хобби'),
        ('finance', 'Финансы'),
        ('rest', 'Отдых'),
        ('sport', 'Спорт'),
        ('other', 'Другое'),
    ]

    word = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Ключевое слово/тема'
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other',
        verbose_name='Категория'
    )

    class Meta:
        verbose_name = 'Ключевое слово'
        verbose_name_plural = 'Ключевые слова'
        ordering = ['word']

    def __str__(self):
        return f"{self.word} ({self.get_category_display()})"

    def get_category_display(self):
        pass


class MoodCorrelation(models.Model):
    """Модель для хранения корреляций между темами и настроением пользователя"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='mood_correlations',
        verbose_name='Пользователь'
    )
    keyword = models.ForeignKey(
        ExtractedKeyword,
        on_delete=models.CASCADE,
        related_name='correlations',
        verbose_name='Ключевое слово'
    )
    correlation_score = models.FloatField(
        validators=[MinValueValidator(-10), MaxValueValidator(10)],
        verbose_name='Коэффициент корреляции',
        help_text='-10: сильная негативная, 0: нет связи, 10: сильная позитивная'
    )
    occurrence_count = models.IntegerField(
        default=0,
        verbose_name='Количество упоминаний'
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name='Последнее обновление'
    )

    class Meta:
        verbose_name = 'Корреляция настроения'
        verbose_name_plural = 'Корреляции настроений'
        unique_together = ['user', 'keyword']  # Одна запись на пользователя+слово
        ordering = ['user', '-correlation_score']

    def __str__(self):
        return f"{self.user.username} - {self.keyword.word}: {self.correlation_score:.2f}"

    def get_correlation_label(self):
        """Возвращает текстовое описание корреляции"""
        if self.correlation_score > 0.3:
            return "Сильная позитивная"
        elif self.correlation_score > 0.1:
            return "Позитивная"
        elif self.correlation_score < -0.3:
            return "Сильная негативная"
        elif self.correlation_score < -0.1:
            return "Негативная"
        else:
            return "Нейтральная"