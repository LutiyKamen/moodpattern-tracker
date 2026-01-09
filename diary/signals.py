from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import DiaryEntry, ExtractedKeyword, MoodCorrelation
from textblob import TextBlob
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

# Дополнительные стоп-слова для нашего контекста
EXTRA_STOPWORDS = {
    'это', 'вот', 'какой', 'который', 'сегодня', 'завтра', 'вчера',
    'очень', 'просто', 'можно', 'нужно', 'будет', 'есть', 'был', 'была',
    'было', 'были', 'весь', 'все', 'всё', 'всего', 'всем', 'сам', 'сама',
    'само', 'сами', 'раз', 'два', 'три', 'четыре', 'пять', 'год', 'года',
    'лет', 'время', 'человек', 'люди', 'жизнь', 'деньги', 'работа',
    'дом', 'город', 'страна', 'мир', 'слово', 'дела', 'руки', 'глаза',
    'вода', 'земля', 'небо', 'солнце', 'луна', 'звезда', 'воздух',
    'огромный', 'маленький', 'большой', 'хороший', 'плохой', 'новый',
    'старый', 'молодой', 'красивый', 'сильный', 'слабый', 'умный',
    'глупый', 'богатый', 'бедный', 'счастливый', 'грустный', 'веселый',
    'серьезный', 'важный', 'нужный', 'возможный', 'необходимый',
    'записи', 'запись', 'записей', 'ключевые', 'ключевых', 'корреляций',
    'корреляции', 'настроение', 'настроения', 'анализ', 'анализа',
    'система', 'системы', 'проект', 'проекта', 'данные', 'данных',
    'пользователь', 'пользователя', 'сервис', 'сервиса', 'дневник',
    'дневника', 'модель', 'модели', 'программа', 'программы',
    'тест', 'теста', 'тестирование', 'тестирования'
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
    # Приводим к нижнему регистру
    text = text.lower()

    # Удаляем знаки препинания, оставляем только русские буквы и пробелы
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\d+', ' ', text)

    # Разделяем на слова
    words = re.findall(r'\b[а-яё]{3,15}\b', text)

    # Фильтруем стоп-слова
    meaningful_words = []
    for word in words:
        if (word not in ALL_STOPWORDS and
                len(word) >= 4 and  # Минимум 4 буквы
                not re.match(r'^[а-яё]+\-[а-яё]+$', word)):  # Исключаем слова с дефисом
            meaningful_words.append(word)

    return meaningful_words


@receiver(post_save, sender=DiaryEntry)
def analyze_diary_entry(sender, instance, created, **kwargs):
    """
    Анализирует дневниковую запись при сохранении
    """
    print(f"\n=== АНАЛИЗ ЗАПИСИ {instance.id} ===")

    try:
        # 1. Анализ тональности
        blob = TextBlob(instance.text)
        sentiment = blob.sentiment
        mood_score = sentiment.polarity

        print(f"Текст: {instance.text[:50]}...")
        print(f"Оценка настроения: {mood_score:.3f}")

        # Сохраняем оценку
        instance.mood_score = mood_score
        instance.word_count = len(instance.text.split())

        # Сохраняем без рекурсии
        DiaryEntry.objects.filter(pk=instance.pk).update(
            mood_score=mood_score,
            word_count=instance.word_count
        )

        # 2. Извлечение значимых слов
        meaningful_words = extract_meaningful_words(instance.text)

        if not meaningful_words:
            print("Не найдено значимых слов")
            return

        print(f"Значимые слова ({len(meaningful_words)}): {meaningful_words[:10]}")

        # 3. Находим самые частые слова (минимум 2 упоминания)
        word_counts = Counter(meaningful_words)

        # Берем слова, которые встречаются хотя бы 2 раза
        significant_words = [(word, count) for word, count in word_counts.items()
                             if count >= 2]

        # Или топ-5 слов, если нет повторяющихся
        if not significant_words and meaningful_words:
            significant_words = word_counts.most_common(5)

        print(f"Значимые для анализа ({len(significant_words)}): {significant_words}")

        # 4. Обрабатываем каждое значимое слово
        for word, count in significant_words:
            # Определяем категорию
            category = get_category_for_word(word)

            # Создаем или получаем ключевое слово
            keyword, kw_created = ExtractedKeyword.objects.get_or_create(
                word=word,
                defaults={'category': category}
            )

            if kw_created:
                print(f"  Новое слово: '{word}' → категория '{category}'")
            else:
                print(f"  Существующее слово: '{word}'")

            # 5. Обновляем корреляцию
            update_mood_correlation(instance.user, keyword, mood_score, count)

        print(f"=== АНАЛИЗ ЗАВЕРШЕН ===\n")

    except Exception as e:
        print(f"ОШИБКА: {str(e)}")
        logger.error(f"Ошибка при анализе записи {instance.id}: {str(e)}")


def update_mood_correlation(user, keyword, mood_score, occurrence_increment=1):
    """
    Обновляет корреляцию между словом и настроением
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
            print(f"    Новая корреляция: {keyword.word} = {mood_score:.3f}")
        else:
            # Взвешенное обновление корреляции
            total_occurrences = correlation.occurrence_count + occurrence_increment

            # Более сильное влияние новых данных
            old_weight = correlation.occurrence_count / (total_occurrences * 1.5)
            new_weight = occurrence_increment / (total_occurrences * 0.5)

            new_correlation = (
                                      correlation.correlation_score * old_weight +
                                      mood_score * new_weight
                              ) / (old_weight + new_weight)

            # Ограничиваем диапазон
            new_correlation = max(-1.0, min(1.0, new_correlation))

            correlation.correlation_score = new_correlation
            correlation.occurrence_count = total_occurrences
            correlation.save()

            print(f"    Обновлена корреляция: {keyword.word} = {new_correlation:.3f} "
                  f"(было {correlation.correlation_score:.3f})")

    except Exception as e:
        print(f"    ОШИБКА корреляции: {str(e)}")


@receiver(post_save, sender=DiaryEntry)
def recalculate_all_correlations(sender, instance, **kwargs):
    """
    Пересчитывает все корреляции пользователя при добавлении нескольких записей
    """
    # Запускаем пересчет только если у пользователя больше 5 записей
    user_entries_count = DiaryEntry.objects.filter(user=instance.user).count()

    if user_entries_count >= 5 and user_entries_count % 5 == 0:
        print(f"\n=== ПЕРЕСЧЕТ КОРРЕЛЯЦИЙ для {instance.user.username} ===")
        recalculate_user_correlations(instance.user)


def recalculate_user_correlations(user):
    """
    Полный пересчет корреляций для пользователя
    """
    from django.db.models import Avg

    # Удаляем старые корреляции
    MoodCorrelation.objects.filter(user=user).delete()

    # Получаем все записи пользователя
    entries = DiaryEntry.objects.filter(user=user)

    if entries.count() < 3:
        return

    # Собираем статистику по всем словам
    word_stats = {}

    for entry in entries:
        if entry.mood_score is None:
            continue

        words = extract_meaningful_words(entry.text)

        for word in set(words):  # Уникальные слова в записи
            if word not in word_stats:
                word_stats[word] = {
                    'mood_scores': [],
                    'count': 0
                }

            word_stats[word]['mood_scores'].append(entry.mood_score)
            word_stats[word]['count'] += 1

    # Создаем корреляции для часто встречающихся слов
    for word, stats in word_stats.items():
        if stats['count'] >= 2:  # Слово должно встречаться минимум в 2 записях
            avg_mood = sum(stats['mood_scores']) / len(stats['mood_scores'])

            # Создаем ключевое слово
            category = get_category_for_word(word)
            keyword, _ = ExtractedKeyword.objects.get_or_create(
                word=word,
                defaults={'category': category}
            )

            # Создаем корреляцию
            MoodCorrelation.objects.create(
                user=user,
                keyword=keyword,
                correlation_score=avg_mood,
                occurrence_count=stats['count']
            )

    print(f"Пересчитано {len(word_stats)} слов, создано корреляций: "
          f"{MoodCorrelation.objects.filter(user=user).count()}")