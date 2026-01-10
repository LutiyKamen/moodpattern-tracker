import os
import django
import random
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moodpattern_tracker.settings')
django.setup()

from django.contrib.auth.models import User
from diary.models import DiaryEntry, ExtractedKeyword, MoodCorrelation

# Получаем или создаем тестового пользователя
user, created = User.objects.get_or_create(
    username='test_analytics',
    defaults={'email': 'test@example.com'}
)

if created:
    user.set_password('test123')
    user.save()
    print(f"Создан пользователь: {user.username}")

# Очищаем старые данные
DiaryEntry.objects.filter(user=user).delete()
MoodCorrelation.objects.filter(user=user).delete()

# Тестовые ключевые слова и их корреляции
test_keywords = [
    {'word': 'работа', 'category': 'work', 'correlation': 0.42},
    {'word': 'друзья', 'category': 'friends', 'correlation': 0.78},
    {'word': 'семья', 'category': 'family', 'correlation': 0.65},
    {'word': 'стресс', 'category': 'work', 'correlation': -0.55},
    {'word': 'болезнь', 'category': 'health', 'correlation': -0.72},
    {'word': 'деньги', 'category': 'finance', 'correlation': -0.35},
    {'word': 'спорт', 'category': 'hobby', 'correlation': 0.58},
    {'word': 'отдых', 'category': 'rest', 'correlation': 0.45},
]

# Создаем ключевые слова и корреляции
for kw_data in test_keywords:
    keyword, _ = ExtractedKeyword.objects.get_or_create(
        word=kw_data['word'],
        defaults={'category': kw_data['category']}
    )

    MoodCorrelation.objects.create(
        user=user,
        keyword=keyword,
        correlation_score=kw_data['correlation'],
        occurrence_count=random.randint(3, 10)
    )

# Создаем тестовые записи за последние 30 дней
base_date = datetime.now() - timedelta(days=30)
mood_patterns = [
    ('excellent', 0.7, 0.9),
    ('good', 0.3, 0.6),
    ('neutral', -0.2, 0.2),
    ('bad', -0.6, -0.3),
    ('terrible', -0.9, -0.7),
]

sample_texts = [
    "Прекрасный день, много успел сделать на работе.",
    "Встреча с друзьями подняла настроение.",
    "Семейный ужин, все были в хорошем расположении духа.",
    "Стресс на работе, дедлайны давят.",
    "Болею, плохо себя чувствую.",
    "Финансовые проблемы вызывают беспокойство.",
    "Тренировка дала заряд энергии.",
    "Отдых на природе помог расслабиться.",
]

for i in range(20):
    # Выбираем случайный паттерн настроения
    mood_tag, mood_min, mood_max = random.choice(mood_patterns)
    mood_score = random.uniform(mood_min, mood_max)

    # Выбираем случайный текст
    text = random.choice(sample_texts)

    # Создаем запись со смещением по времени
    entry_date = base_date + timedelta(days=random.randint(0, 30))

    DiaryEntry.objects.create(
        user=user,
        text=text,
        user_mood_tag=mood_tag,
        mood_score=mood_score,
        word_count=len(text.split()),
        date_created=entry_date
    )

print(f"Создано тестовых данных:")
print(f"- Записей: {DiaryEntry.objects.filter(user=user).count()}")
print(f"- Корреляций: {MoodCorrelation.objects.filter(user=user).count()}")
print("\nВойдите как test_analytics / test123 для проверки аналитики")