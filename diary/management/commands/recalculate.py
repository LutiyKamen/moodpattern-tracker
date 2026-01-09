from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from diary.models import DiaryEntry, MoodCorrelation, ExtractedKeyword
import re
from collections import defaultdict


class Command(BaseCommand):
    help = 'Пересчитывает все корреляции настроения для всех пользователей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Пересчитать только для конкретного пользователя'
        )

    def handle(self, *args, **options):
        if options['username']:
            try:
                user = User.objects.get(username=options['username'])
                self.recalculate_for_user(user)
                self.stdout.write(
                    self.style.SUCCESS(f'Пересчет завершен для пользователя {user.username}')
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Пользователь {options["username"]} не найден')
                )
        else:
            self.stdout.write('Начинаю пересчет корреляций для всех пользователей...')
            users = User.objects.all()

            for user in users:
                self.recalculate_for_user(user)

            self.stdout.write(
                self.style.SUCCESS(f'Пересчет завершен для {users.count()} пользователей')
            )

    def extract_meaningful_words(self, text):
        """Извлекает значимые слова из текста (упрощенная версия)"""
        # Приводим к нижнему регистру
        text = text.lower()

        # Удаляем знаки препинания и цифры
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\d+', ' ', text)

        # Разделяем на слова (русские, 3-15 букв)
        words = re.findall(r'\b[а-яё]{3,15}\b', text)

        # Стоп-слова
        stop_words = {
            'это', 'вот', 'какой', 'который', 'сегодня', 'завтра', 'вчера',
            'очень', 'просто', 'можно', 'нужно', 'будет', 'есть', 'был',
            'была', 'было', 'были', 'весь', 'все', 'всё', 'сам', 'сама',
            'само', 'сами', 'раз', 'два', 'три', 'год', 'года', 'лет',
            'человек', 'люди', 'жизнь', 'деньги', 'дом', 'город', 'страна',
            'мир', 'слово', 'дела', 'руки', 'глаза', 'вода', 'земля',
            'небо', 'солнце', 'луна', 'звезда', 'воздух', 'записи',
            'запись', 'ключевые', 'корреляций', 'настроение', 'анализ',
            'система', 'проект', 'данные', 'пользователь', 'сервис',
            'дневник', 'модель', 'программа', 'тест', 'тестирование',
            'может', 'хотя', 'когда', 'потому', 'такой', 'такие', 'такая',
            'такое', 'таким', 'такими', 'каждая', 'каждое', 'каждый'
        }

        # Фильтруем стоп-слова и короткие слова
        meaningful_words = []
        for word in words:
            if (word not in stop_words and
                    len(word) >= 4 and  # минимум 4 буквы
                    not word.endswith('ться') and  # исключаем инфинитивы
                    not word.endswith('тся')):
                meaningful_words.append(word)

        return meaningful_words

    def get_category_for_word(self, word):
        """Определяет категорию для слова"""
        categories = {
            'work': ['работа', 'проект', 'задача', 'дедлайн', 'начальник',
                     'коллега', 'офис', 'зарплата', 'совещание', 'отчет'],
            'study': ['учеба', 'университет', 'курс', 'экзамен', 'зачет'],
            'family': ['семья', 'родители', 'мама', 'папа', 'брат', 'сестра'],
            'friends': ['друзья', 'друг', 'подруга', 'встреча', 'общение'],
            'health': ['здоровье', 'болезнь', 'врач', 'боль', 'лечение'],
            'hobby': ['хобби', 'спорт', 'музыка', 'кино', 'книга', 'чтение'],
            'finance': ['деньги', 'зарплата', 'покупка', 'траты', 'экономия'],
            'rest': ['отдых', 'отпуск', 'каникулы', 'выходные', 'сон'],
        }

        for category, keywords in categories.items():
            if word in keywords:
                return category

        return 'other'

    def recalculate_for_user(self, user):
        """Пересчитывает корреляции для одного пользователя"""
        # Получаем все записи пользователя
        entries = DiaryEntry.objects.filter(user=user).exclude(mood_score__isnull=True)

        if entries.count() < 3:
            self.stdout.write(f'  {user.username}: пропущен (мало записей: {entries.count()})')
            return

        self.stdout.write(f'  {user.username}: анализирую {entries.count()} записей...')

        # Удаляем старые корреляции пользователя
        deleted_count, _ = MoodCorrelation.objects.filter(user=user).delete()
        if deleted_count:
            self.stdout.write(f'    Удалено старых корреляций: {deleted_count}')

        # Собираем статистику по словам
        word_stats = defaultdict(lambda: {'mood_scores': [], 'count': 0})

        for entry in entries:
            words = self.extract_meaningful_words(entry.text)

            # Используем set чтобы учитывать слово только один раз в записи
            for word in set(words):
                word_stats[word]['mood_scores'].append(entry.mood_score)
                word_stats[word]['count'] += 1

        # Создаем корреляции для часто встречающихся слов
        created_count = 0
        for word, stats in word_stats.items():
            # Слово должно встречаться минимум в 2 разных записях
            if stats['count'] >= 2 and len(stats['mood_scores']) >= 2:
                # Среднее настроение при упоминании этого слова
                avg_mood = sum(stats['mood_scores']) / len(stats['mood_scores'])

                # Определяем категорию
                category = self.get_category_for_word(word)

                # Создаем или получаем ключевое слово
                keyword, created = ExtractedKeyword.objects.get_or_create(
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
                created_count += 1

        self.stdout.write(
            f'    Создано корреляций: {created_count} '
            f'(обработано {len(word_stats)} уникальных слов)'
        )