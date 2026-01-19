from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import DiaryEntry, ExtractedKeyword, MoodCorrelation
from .analysis_utils import analyze_text_sentiment, extract_keywords
import re
from collections import Counter
import logging
import nltk
from nltk.corpus import stopwords

logger = logging.getLogger(__name__)

# Скачиваем стоп-слова при первом запуске
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# Русские стоп-слова
RUSSIAN_STOPWORDS = set(stopwords.words('russian'))

# Дополнительные стоп-слова
EXTRA_STOPWORDS = {
    'это', 'вот', 'какой', 'который', 'сегодня', 'завтра', 'вчера',
    'очень', 'просто', 'можно', 'нужно', 'будет', 'есть', 'был', 'была',
    'было', 'были', 'весь', 'все', 'всё', 'всего', 'всем', 'сам', 'сама',
    'само', 'сами', 'раз', 'два', 'три', 'четыре', 'пять', 'год', 'года',
    'лет', 'время', 'человек', 'люди', 'жизнь', 'деньги', 'работа',
    'дом', 'город', 'страна', 'мир', 'слово', 'дела', 'руки', 'глаза',
}

ALL_STOPWORDS = RUSSIAN_STOPWORDS.union(EXTRA_STOPWORDS)

# Категории для автоматической классификации
CATEGORY_KEYWORDS = {
    'work': ['работа', 'проект', 'задача', 'дедлайн', 'начальник', 'коллега',
             'офис', 'зарплата', 'совещание', 'отчет', 'клиент', 'бизнес'],
    'study': ['учеба', 'университет', 'курс', 'экзамен', 'зачет', 'лекция',
              'преподаватель', 'студент', 'обучение', 'знания', 'диплом'],
    'family': ['семья', 'родители', 'мама', 'папа', 'брат', 'сестра',
               'дети', 'ребенок', 'муж', 'жена', 'бабушка', 'дедушка'],
    'friends': ['друзья', 'друг', 'подруга', 'компания', 'встреча',
                'общение', 'разговор', 'вечеринка', 'праздник'],
    'health': ['здоровье', 'болезнь', 'врач', 'боль', 'лечение', 'таблетки',
               'аптека', 'симптомы', 'диагноз', 'больница', 'анализы'],
    'hobby': ['хобби', 'спорт', 'музыка', 'кино', 'книга', 'чтение',
              'рисование', 'программирование', 'путешествие', 'фотография'],
    'finance': ['деньги', 'зарплата', 'покупка', 'траты', 'экономия',
                'бюджет', 'счет', 'банк', 'кредит', 'долг', 'инвестиции'],
    'rest': ['отдых', 'отпуск', 'каникулы', 'выходные', 'сон', 'релакс',
             'медитация', 'прогулка', 'парк', 'природа', 'море'],
}


def get_category_for_word(word):
    """Определяет категорию для слова"""
    for category, keywords in CATEGORY_KEYWORDS.items():
        if word in keywords:
            return category
    return 'other'


def extract_meaningful_words(text):
    """Извлекает значимые слова из текста"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\d+', ' ', text)

    words = re.findall(r'\b[а-яё]{3,15}\b', text)

    meaningful_words = []
    for word in words:
        if (word not in ALL_STOPWORDS and
                len(word) >= 4):
            meaningful_words.append(word)

    return meaningful_words


@receiver(post_save, sender=DiaryEntry)
def analyze_diary_entry_on_save(instance):
    """Анализирует дневниковую запись при сохранении"""
    try:
        # Анализируем тональность
        mood_score = analyze_text_sentiment(instance.text)

        # Обновляем запись без рекурсии
        DiaryEntry.objects.filter(pk=instance.pk).update(
            mood_score=mood_score,
            word_count=len(instance.text.split())
        )

        logger.info(f"Запись {instance.id} проанализирована. Настроение: {mood_score:.2f}")

        # Извлекаем ключевые слова
        keywords = extract_keywords(instance.text)
        word_counts = Counter(keywords)

        # Обрабатываем каждое слово
        for word, count in word_counts.items():
            if count >= 1:  # Минимум 1 упоминание
                category = get_category_for_word(word)

                # Создаем или получаем ключевое слово
                keyword, _ = ExtractedKeyword.objects.get_or_create(
                    word=word,
                    defaults={'category': category}
                )

                # Обновляем корреляцию
                update_mood_correlation(instance.user, keyword, mood_score, count)

    except Exception as e:
        logger.error(f"Ошибка при анализе записи {instance.id}: {str(e)}")


def update_mood_correlation(user, keyword, mood_score, occurrence_increment=1):
    """Обновляет корреляцию между словом и настроением"""
    try:
        correlation, created = MoodCorrelation.objects.get_or_create(
            user=user,
            keyword=keyword,
            defaults={
                'correlation_score': mood_score,
                'occurrence_count': occurrence_increment
            }
        )

        if not created:
            # Обновляем существующую корреляцию
            total_occurrences = correlation.occurrence_count + occurrence_increment

            # Взвешенное обновление (шкала -10..10)
            old_weight = correlation.occurrence_count / total_occurrences
            new_weight = occurrence_increment / total_occurrences

            new_correlation = (
                    correlation.correlation_score * old_weight +
                    mood_score * new_weight
            )

            # Ограничиваем диапазон -10..10
            new_correlation = max(-10.0, min(10.0, new_correlation))

            correlation.correlation_score = new_correlation
            correlation.occurrence_count = total_occurrences
            correlation.save()

    except Exception as e:
        logger.error(f"Ошибка при обновлении корреляции: {str(e)}")


@receiver(post_delete, sender=DiaryEntry)
def handle_entry_deletion(instance):
    """Обрабатывает удаление записи"""
    try:
        logger.info(f"Запись {instance.id} удалена пользователем {instance.user.username}")
    except Exception as e:
        logger.error(f"Ошибка при обработке удаления записи: {str(e)}")

def recalculate_user_correlations(user):
    """Полный пересчет корреляций для пользователя"""

    try:
        # Удаляем старые корреляции
        MoodCorrelation.objects.filter(user=user).delete()

        # Получаем все записи пользователя
        entries = DiaryEntry.objects.filter(user=user).exclude(mood_score__isnull=True)

        if entries.count() < 3:
            return

        # Собираем статистику по всем словам
        word_stats = {}

        for entry in entries:
            words = extract_meaningful_words(entry.text)

            for word in set(words):
                if word not in word_stats:
                    word_stats[word] = {
                        'mood_scores': [],
                        'count': 0
                    }

                word_stats[word]['mood_scores'].append(entry.mood_score)
                word_stats[word]['count'] += 1

        # Создаем корреляции для часто встречающихся слов
        for word, stats in word_stats.items():
            if stats['count'] >= 2:
                avg_mood = sum(stats['mood_scores']) / len(stats['mood_scores'])

                category = get_category_for_word(word)
                keyword, _ = ExtractedKeyword.objects.get_or_create(
                    word=word,
                    defaults={'category': category}
                )

                MoodCorrelation.objects.create(
                    user=user,
                    keyword=keyword,
                    correlation_score=avg_mood,
                    occurrence_count=stats['count']
                )

        logger.info(f"Пересчет корреляций для {user.username} завершен")

    except Exception as e:
        logger.error(f"Ошибка при пересчете корреляций: {str(e)}")