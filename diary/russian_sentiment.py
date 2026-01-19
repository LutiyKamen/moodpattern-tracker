import re
import os


def _load_stopwords():
    """Загружает русские стоп-слова"""
    return {
        'это', 'вот', 'какой', 'который', 'сегодня', 'завтра', 'вчера',
        'просто', 'можно', 'нужно', 'будет', 'есть', 'был', 'была',
        'было', 'были', 'весь', 'все', 'всё', 'всего', 'всем', 'сам', 'сама',
        'само', 'сами', 'раз', 'два', 'три', 'год', 'года', 'лет',
        'как', 'так', 'там', 'здесь', 'тут', 'где', 'куда', 'откуда',
        'почему', 'зачем', 'сколько', 'когда', 'что', 'чтобы', 'если'
    }


def _load_categories():
    """Категории слов для лучшего анализа"""
    return {
        # Эмоции
        'emotion_positive': {'счастлив', 'радост', 'весел', 'доволен'},
        'emotion_negative': {'грустн', 'печальн', 'тосклив', 'зл', 'сердит'},

        # Состояния
        'state_positive': {'здоров', 'сильн', 'энергичн', 'бодр'},
        'state_negative': {'больн', 'устал', 'слаб', 'утомлен'},

        # События
        'event_positive': {'праздник', 'подарок', 'награда', 'успех'},
        'event_negative': {'проблем', 'конфликт', 'ссор', 'неудач'},

        # Социальное
        'social_positive': {'друг', 'семья', 'любовь', 'поддержк'},
        'social_negative': {'одинок', 'конфликт', 'ссор', 'измен'},
    }


def _get_default_words(filename):
    """Базовые наборы слов если файлы не найдены"""
    defaults = {
        'positive_ru.txt': {
            'хорош', 'отличн', 'прекрасн', 'замечательн', 'великолепн',
            'счастлив', 'радост', 'весел', 'доволен', 'успешн'
        },
        'negative_ru.txt': {
            'плох', 'ужасн', 'отвратительн', 'грустн', 'печальн',
            'зл', 'сердит', 'больн', 'устал', 'проблем'
        },
        'intensifiers_ru.txt': {'очень', 'сильно', 'крайне', 'чрезвычайно'},
        'negations_ru.txt': {'не', 'ни', 'нет', 'без'}
    }
    return defaults.get(filename, set())


def preprocess_text(text):
    """Подготовка текста: очистка, токенизация"""
    # Приводим к нижнему регистру
    text = text.lower()

    # Заменяем ё на е
    text = text.replace('ё', 'е')

    # Удаляем лишние пробелы
    text = re.sub(r'\s+', ' ', text)

    return text


def stem_word(word):
    """Упрощенный стемминг русских слов"""
    if len(word) < 4:
        return word

    # Общие окончания
    endings = ['ый', 'ий', 'ой', 'ая', 'яя', 'ое', 'ее', 'ые', 'ие',
               'ость', 'ация', 'ение', 'анье', 'ство', 'изм',
               'нно', 'енно', 'ально']

    for ending in endings:
        if word.endswith(ending):
            return word[:-len(ending)]

    return word


def _score_to_sentiment(score):
    """Преобразует числовую оценку в текстовое описание"""
    if score > 7:
        return "очень позитивный"
    elif score > 3:
        return "позитивный"
    elif score > 1:
        return "слегка позитивный"
    elif score > -1:
        return "нейтральный"
    elif score > -3:
        return "слегка негативный"
    elif score > -7:
        return "негативный"
    else:
        return "очень негативный"


class AdvancedRussianSentimentAnalyzer:
    """Продвинутый анализатор тональности для русского текста"""

    def __init__(self, data_dir='diary/sentiment_data'):
        self.data_dir = data_dir

        # Загружаем словари
        self.positive_words = self._load_wordlist('positive_ru.txt')
        self.negative_words = self._load_wordlist('negative_ru.txt')
        self.intensifiers = self._load_wordlist('intensifiers_ru.txt')
        self.negations = self._load_wordlist('negations_ru.txt')

        # Стоп-слова
        self.stopwords = _load_stopwords()

        # Веса для разных типов слов
        self.weights = {
            'positive': 1.0,
            'negative': -1.0,
            'intensifier': 1.5,  # усиливает следующее слово
            'negation': -1.0,  # инвертирует следующее слово
        }

        # Эмоциональные паттерны
        self.emotional_patterns = [
            (r'!{2,}', 1.3),  # Восклицания !!
            (r'\?{2,}', -0.5),  # Много вопросов ??
            (r'\.{3,}', -0.7),  # Многоточие ...
            (r'[A-ZА-Я]{4,}', 0.8),  # КАПСЛОК
            (r'[♥♡❤️💕💖]', 1.2),  # Сердечки
            (r'[😊😂🤣😍🥰]', 1.5),  # Позитивные эмодзи
            (r'[😢😭😔😞😠]', -1.5),  # Негативные эмодзи
        ]

        # Категории слов для лучшего анализа
        self.word_categories = _load_categories()

    def _load_wordlist(self, filename):
        """Загружает список слов из файла"""
        filepath = os.path.join(self.data_dir, filename)
        words = set()

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip().lower()
                    if word and not word.startswith('#'):
                        words.add(word)
            print(f"✓ Загружено {len(words)} слов из {filename}")
        except FileNotFoundError:
            print(f"⚠ Файл {filename} не найден, использую базовый набор")
            words = _get_default_words(filename)

        return words

    def tokenize(self, text):
        """Токенизация текста с учетом особенностей русского"""
        # Разбиваем на слова, сохраняем знаки препинания отдельно
        tokens = re.findall(r'\b[а-яё]+\b|[!?.,;:]+', text)

        # Фильтруем стоп-слова и короткие слова
        tokens = [t for t in tokens if t not in self.stopwords and len(t) > 2]

        return tokens

    def analyze_sentiment(self, text):
        """Основной метод анализа тональности"""
        if not text or len(text.strip()) < 3:
            return 0.0, []

        # Подготовка текста
        text = preprocess_text(text)

        # Токенизация
        tokens = self.tokenize(text)

        if not tokens:
            return 0.0, []

        # Анализ каждого токена
        score = 0.0
        sentiment_words = []
        i = 0

        while i < len(tokens):
            token = tokens[i]
            token_score = 0.0
            multiplier = 1.0

            # Проверяем усилители
            if token in self.intensifiers:
                if i + 1 < len(tokens):
                    next_token = tokens[i + 1]
                    # Усилитель влияет на следующее слово
                    multiplier = self.weights['intensifier']
                    i += 1
                    token = next_token

            # Проверяем отрицания
            if token in self.negations:
                if i + 1 < len(tokens):
                    next_token = tokens[i + 1]
                    # Отрицание инвертирует следующее слово
                    multiplier *= self.weights['negation']
                    i += 1
                    token = next_token

            # Определяем тональность слова
            stemmed = stem_word(token)

            if stemmed in self.positive_words or any(pos in stemmed for pos in self.positive_words):
                token_score = self.weights['positive']
                sentiment_words.append((token, token_score * multiplier))
            elif stemmed in self.negative_words or any(neg in stemmed for neg in self.negative_words):
                token_score = self.weights['negative']
                sentiment_words.append((token, token_score * multiplier))

            # Учитываем длину слова (длинные слова обычно значимее)
            if len(token) > 6:
                token_score *= 1.1

            # Применяем множитель
            token_score *= multiplier

            score += token_score
            i += 1

        # Учитываем эмоциональные паттерны
        pattern_score = self._analyze_patterns(text)
        score += pattern_score

        # Нормализация
        if sentiment_words:
            avg_score = score / len(sentiment_words)
            normalized_score = avg_score * 10  # Масштабируем до -10..10
        else:
            normalized_score = 0.0

        # Ограничение диапазона
        normalized_score = max(-10.0, min(10.0, normalized_score))

        return round(normalized_score, 2), sentiment_words

    def _analyze_patterns(self, text):
        """Анализ эмоциональных паттернов в тексте"""
        pattern_score = 0.0

        for pattern, weight in self.emotional_patterns:
            matches = re.findall(pattern, text)
            if matches:
                pattern_score += len(matches) * weight

        # Учитываем длину текста
        words_count = len(text.split())
        if words_count > 0:
            # Более длинные тексты имеют больший вес
            length_factor = min(2.0, words_count / 50)
            pattern_score *= length_factor

        return pattern_score

    def get_detailed_analysis(self, text):
        """Детальный анализ с разбивкой по категориям"""
        score, sentiment_words = self.analyze_sentiment(text)

        analysis = {
            'overall_score': score,
            'sentiment': _score_to_sentiment(score),
            'word_count': len(text.split()),
            'sentiment_words_count': len(sentiment_words),
            'sentiment_words': sentiment_words,
            'positive_words': [w for w, s in sentiment_words if s > 0],
            'negative_words': [w for w, s in sentiment_words if s < 0],
            'intensity': abs(score),
        }

        return analysis


# Создаем глобальный экземпляр для удобства
analyzer = AdvancedRussianSentimentAnalyzer()


# Функция для импорта
def analyze_russian_sentiment(text):
    """Упрощенный интерфейс для анализа"""
    score, _ = analyzer.analyze_sentiment(text)
    return score