from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import DiaryEntry, ExtractedKeyword, MoodCorrelation
from textblob import TextBlob
import re
from collections import Counter
import logging

# Настройка логгирования
logger = logging.getLogger(__name__)


@receiver(post_save, sender=DiaryEntry)
def analyze_diary_entry(sender, instance, created, **kwargs):
    """
    Анализирует дневниковую запись при сохранении
    """
    print(f"=== СИГНАЛ СРАБОТАЛ для записи {instance.id} ===")
    logger.info(f"Сработал сигнал для записи {instance.id}, создано: {created}")

    try:
        # 1. Анализ тональности с помощью TextBlob
        print("Анализирую текст...")
        blob = TextBlob(instance.text)
        sentiment = blob.sentiment
        mood_score = sentiment.polarity  # от -1 до 1

        print(f"Тональность TextBlob: полярность={sentiment.polarity}, субъективность={sentiment.subjectivity}")

        # 2. Сохраняем оценку
        instance.mood_score = mood_score
        instance.word_count = len(instance.text.split())

        # Сохраняем без вызова сигнала (avoid recursion)
        DiaryEntry.objects.filter(pk=instance.pk).update(
            mood_score=mood_score,
            word_count=instance.word_count
        )

        print(f"Сохранено: mood_score={mood_score}, word_count={instance.word_count}")

        # 3. Извлечение ключевых слов (для русского текста)
        print("Извлекаю ключевые слова...")

        # Простая очистка текста
        text_lower = instance.text.lower()

        # Удаляем пунктуацию и разделяем на слова
        words = re.findall(r'\b[а-яё]{4,}\b', text_lower)

        # Список стоп-слов (часто встречающиеся слова)
        stop_words = {
            'этот', 'это', 'вот', 'какой', 'который', 'сегодня', 'завтра',
            'вчера', 'очень', 'просто', 'можно', 'нужно', 'будет', 'есть',
            'что', 'как', 'где', 'когда', 'потом', 'тогда', 'здесь', 'там'
        }

        # Фильтруем стоп-слова
        keywords = [word for word in words if word not in stop_words]

        print(f"Найдено слов после фильтрации: {len(keywords)}")

        if keywords:
            # Подсчитываем частоту
            word_counts = Counter(keywords)
            top_keywords = word_counts.most_common(3)  # Берем топ-3

            print(f"Топ-ключевые слова: {top_keywords}")

            # 4. Создаем/получаем ключевые слова
            for word, count in top_keywords:
                keyword, created_kw = ExtractedKeyword.objects.get_or_create(
                    word=word,
                    defaults={'category': 'other'}
                )

                print(f"Ключевое слово: '{word}', создано: {created_kw}")

                # 5. Обновляем корреляцию
                update_mood_correlation(instance.user, keyword, mood_score, 1)

        print(f"=== АНАЛИЗ ЗАВЕРШЕН для записи {instance.id} ===\n")

    except Exception as e:
        print(f"ОШИБКА при анализе записи {instance.id}: {str(e)}")
        logger.error(f"Ошибка при анализе записи {instance.id}: {str(e)}")


def update_mood_correlation(user, keyword, mood_score, occurrence_increment=1):
    """
    Обновляет корреляцию между словом и настроением пользователя
    """
    try:
        correlation, created = MoodCorrelation.objects.get_or_create(
            user=user,
            keyword=keyword,
            defaults={
                'correlation_score': mood_score,
                'occurrence_count': occurrence_increment
            }
        )

        if created:
            print(f"Создана новая корреляция: {user.username} - {keyword.word}")
        else:
            # Простое обновление: среднее арифметическое
            total_occurrences = correlation.occurrence_count + occurrence_increment
            new_correlation = (
                                      (correlation.correlation_score * correlation.occurrence_count) +
                                      (mood_score * occurrence_increment)
                              ) / total_occurrences

            correlation.correlation_score = new_correlation
            correlation.occurrence_count = total_occurrences
            correlation.save()

            print(f"Обновлена корреляция: {user.username} - {keyword.word} = {new_correlation:.3f}")

    except Exception as e:
        print(f"ОШИБКА при обновлении корреляции: {str(e)}")
        logger.error(f"Ошибка при обновлении корреляции: {str(e)}")


@receiver(post_delete, sender=DiaryEntry)
def cleanup_mood_correlations(sender, instance, **kwargs):
    """
    Очищает корреляции при удалении записи
    """
    print(f"Запись {instance.id} удалена, очистка корреляций...")
    # В упрощённой версии оставляем пустым