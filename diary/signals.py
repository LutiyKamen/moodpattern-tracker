from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import DiaryEntry, ExtractedKeyword, MoodCorrelation
from textblob import TextBlob
import re
from collections import Counter


@receiver(post_save, sender=DiaryEntry)
def analyze_diary_entry(sender, instance, created, **kwargs):
    """
    Анализирует дневниковую запись при сохранении:
    1. Определяет тональность текста
    2. Извлекает ключевые слова
    3. Обновляет статистику корреляций
    """
    # 1. Анализ тональности с помощью TextBlob
    blob = TextBlob(instance.text)
    sentiment = blob.sentiment
    instance.mood_score = sentiment.polarity  # от -1 до 1
    instance.word_count = len(instance.text.split())

    # Сохраняем обновлённые поля, избегая рекурсии
    DiaryEntry.objects.filter(pk=instance.pk).update(
        mood_score=instance.mood_score,
        word_count=instance.word_count
    )

    # 2. Извлечение ключевых слов (простые существительные)
    # Для русского текста нужна дополнительная обработка
    words = re.findall(r'\b[а-яА-Я]{4,}\b', instance.text.lower())
    common_words = {'этот', 'это', 'вот', 'какой', 'который', 'сегодня', 'завтра', 'вчера'}
    keywords = [word for word in words if word not in common_words]

    # Берем топ-5 самых частых слов
    word_counts = Counter(keywords)
    top_keywords = word_counts.most_common(5)

    # 3. Создаем или получаем ключевые слова
    for word, count in top_keywords:
        keyword, _ = ExtractedKeyword.objects.get_or_create(
            word=word,
            defaults={'category': 'other'}
        )

        # 4. Обновляем корреляцию для этого пользователя и слова
        update_mood_correlation(instance.user, keyword, instance.mood_score, count)


def update_mood_correlation(user, keyword, mood_score, occurrence_increment=1):
    """
    Обновляет корреляцию между словом и настроением пользователя
    """
    correlation, created = MoodCorrelation.objects.get_or_create(
        user=user,
        keyword=keyword,
        defaults={
            'correlation_score': mood_score,
            'occurrence_count': occurrence_increment
        }
    )

    if not created:
        # Простой метод обновления корреляции: взвешенное среднее
        total_occurrences = correlation.occurrence_count + occurrence_increment
        # Взвешиваем старую и новую оценку
        old_weight = correlation.occurrence_count / total_occurrences
        new_weight = occurrence_increment / total_occurrences

        new_correlation = (
                correlation.correlation_score * old_weight +
                mood_score * new_weight
        )

        correlation.correlation_score = new_correlation
        correlation.occurrence_count = total_occurrences
        correlation.save()


@receiver(post_delete, sender=DiaryEntry)
def cleanup_mood_correlations(sender, instance, **kwargs):
    """
    Очищает корреляции при удалении записи
    (В реальном проекте здесь была бы более сложная логика)
    """
    # В упрощённой версии просто уменьшаем счетчики
    # Для MVP можно оставить пустым или реализовать позже
    pass