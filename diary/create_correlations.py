import os
import sys
import django
from django.contrib.auth.models import User

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moodpattern_tracker.settings')
django.setup()

from diary.models import ExtractedKeyword, MoodCorrelation


def create_test_correlations(username=None):
    """Создает тестовые корреляции для пользователя"""

    if username:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            print(f"\n❌ Пользователь '{username}' не найден!")
            print("\nДоступные пользователи:")
            for u in User.objects.all():
                print(f"  - {u.username}")
            return
    else:
        # Берем первого пользователя
        users = User.objects.all()
        if not users.exists():
            print("❌ Нет пользователей в системе!")
            print("Сначала создайте пользователя через регистрацию или админку")
            return
        user = users.first()
        username = user.username

    print(f"Найден пользователь: {user.username} (ID: {user.id})")

    # Удаляем старые корреляции
    deleted_count, _ = MoodCorrelation.objects.filter(user=user).delete()
    print(f"Удалено старых корреляций: {deleted_count}")

    # Тестовые данные
    test_correlations = [
        # Позитивные
        {'word': 'работа', 'category': 'work', 'correlation': 0.42, 'count': 8},
        {'word': 'друзья', 'category': 'friends', 'correlation': 0.78, 'count': 12},
        {'word': 'семья', 'category': 'family', 'correlation': 0.65, 'count': 10},
        {'word': 'спорт', 'category': 'sport', 'correlation': 0.58, 'count': 6},
        {'word': 'отдых', 'category': 'rest', 'correlation': 0.45, 'count': 5},
        {'word': 'музыка', 'category': 'hobby', 'correlation': 0.32, 'count': 4},

        # Негативные
        {'word': 'стресс', 'category': 'work', 'correlation': -0.55, 'count': 7},
        {'word': 'болезнь', 'category': 'health', 'correlation': -0.72, 'count': 4},
        {'word': 'деньги', 'category': 'finance', 'correlation': -0.35, 'count': 5},
        {'word': 'конфликт', 'category': 'work', 'correlation': -0.48, 'count': 3},
        {'word': 'усталость', 'category': 'health', 'correlation': -0.61, 'count': 6},
        {'word': 'проблемы', 'category': 'other', 'correlation': -0.28, 'count': 5},
    ]

    created_count = 0
    for data in test_correlations:
        keyword, created = ExtractedKeyword.objects.get_or_create(
            word=data['word'],
            defaults={'category': data['category']}
        )

        if created:
            print(f"  Создано ключевое слово: '{data['word']}'")

        correlation, corr_created = MoodCorrelation.objects.get_or_create(
            user=user,
            keyword=keyword,
            defaults={
                'correlation_score': data['correlation'],
                'occurrence_count': data['count']
            }
        )

        if corr_created:
            created_count += 1

    print(f"\n✅ Создано {created_count} корреляций")

    # Выводим результаты
    correlations = MoodCorrelation.objects.filter(user=user)

    print("\n📊 Позитивные триггеры:")
    pos = correlations.filter(correlation_score__gt=0).order_by('-correlation_score')
    for c in pos[:5]:
        print(f"  + {c.keyword.word}: {c.correlation_score:.2f} (упоминаний: {c.occurrence_count})")

    print("\n📉 Негативные триггеры:")
    neg = correlations.filter(correlation_score__lt=0).order_by('correlation_score')
    for c in neg[:5]:
        print(f"  - {c.keyword.word}: {c.correlation_score:.2f} (упоминаний: {c.occurrence_count})")

    print(f"\n✅ Готово! Всего корреляций: {correlations.count()}")
    print(f"Откройте аналитику на сайте для пользователя {username}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Создание тестовых корреляций')
    parser.add_argument('--username', '-u', help='Имя пользователя', default=None)

    args = parser.parse_args()

    create_test_correlations(args.username)