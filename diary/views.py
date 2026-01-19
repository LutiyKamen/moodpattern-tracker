from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.paginator import Paginator
from django.db.models import Avg
from datetime import datetime, timedelta, date

from .models import DiaryEntry, MoodCorrelation
from .forms import DiaryEntryForm, UserRegisterForm, UserLoginForm
from .analysis_utils import (
    calculate_statistics,
    create_mood_timeline_chart,
    create_weekday_chart,
    create_mood_distribution_chart
)


def home(request):
    """Главная страница"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    context = {
        'demo_data': {
            'total_entries': 1250,
            'avg_mood': 0.35,
            'top_triggers': [
                {'word': 'работа', 'correlation': -0.42},
                {'word': 'друзья', 'correlation': 0.78},
                {'word': 'спорт', 'correlation': 0.65},
            ]
        }
    }
    return render(request, 'diary/home.html', context)


def register_view(request):
    """Регистрация"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                login(request, user)
                messages.success(request, 'Регистрация прошла успешно!')
                return redirect('dashboard')
            except Exception as e:
                # Логируем ошибку для отладки
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при регистрации: {str(e)}")
                messages.error(request, f'Ошибка при регистрации: {str(e)}')
        else:
            # Показываем ошибки формы
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UserRegisterForm()

    return render(request, 'diary/register.html', {'form': form})


def login_view(request):
    """Авторизация"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('dashboard')
    else:
        form = UserLoginForm()

    return render(request, 'diary/login.html', {'form': form})


@login_required
def logout_view(request):
    """Выход"""
    logout(request)
    messages.info(request, 'Вы успешно вышли из системы.')
    return redirect('home')


@login_required
def dashboard(request):
    """Личный кабинет"""
    # Записи пользователя
    entries = DiaryEntry.objects.filter(user=request.user).order_by('-date_created')

    # Пагинация
    paginator = Paginator(entries, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Статистика
    total_entries = entries.count()
    entries_with_score = entries.exclude(mood_score__isnull=True)

    if entries_with_score.exists():
        avg_mood = entries_with_score.aggregate(Avg('mood_score'))['mood_score__avg'] or 0
    else:
        avg_mood = 0

    # Записи за сегодня
    today_entries = entries.filter(date_created__date=date.today()).count()

    # Топ-триггеры
    top_correlations = MoodCorrelation.objects.filter(
        user=request.user,
        occurrence_count__gte=2
    ).order_by('-correlation_score')[:3]

    # График за 7 дней
    mood_chart_html = None
    if entries_with_score.count() > 1:
        try:
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_entries = entries_with_score.filter(date_created__gte=seven_days_ago)

            if recent_entries.count() >= 2:
                mood_chart_html = create_mood_timeline_chart(recent_entries)

        except Exception as e:
            print(f"Ошибка графика: {e}")
            mood_chart_html = None

    context = {
        'page_obj': page_obj,
        'total_entries': total_entries,
        'avg_mood': avg_mood,
        'today_entries': today_entries,
        'top_correlations': top_correlations,
        'mood_chart_html': mood_chart_html,
    }

    return render(request, 'diary/dashboard.html', context)


@login_required
def create_entry(request):
    """Создание записи"""
    if request.method == 'POST':
        form = DiaryEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            messages.success(request, 'Запись успешно добавлена!')
            return redirect('dashboard')
    else:
        form = DiaryEntryForm()

    return render(request, 'diary/entry_form.html', {'form': form, 'title': 'Новая запись'})


@login_required
def edit_entry(request, entry_id):
    """Редактирование записи"""
    entry = get_object_or_404(DiaryEntry, id=entry_id, user=request.user)

    if request.method == 'POST':
        form = DiaryEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, 'Запись успешно обновлена!')
            return redirect('dashboard')
    else:
        form = DiaryEntryForm(instance=entry)

    return render(request, 'diary/entry_form.html', {'form': form, 'title': 'Редактировать запись'})


@login_required
def delete_entry(request, entry_id):
    """Удаление записи"""
    entry = get_object_or_404(DiaryEntry, id=entry_id, user=request.user)

    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Запись успешно удалена.')
        return redirect('dashboard')

    return render(request, 'diary/confirm_delete.html', {'entry': entry})


@login_required
def analytics(request):
    """Аналитика с пагинацией"""
    # Получаем данные
    entries = DiaryEntry.objects.filter(user=request.user)
    all_correlations = MoodCorrelation.objects.filter(user=request.user)

    # 1. Положительные корреляции с пагинацией
    positive_correlations = all_correlations.filter(
        correlation_score__gt=0.5
    ).order_by('-correlation_score')

    positive_paginator = Paginator(positive_correlations, 15)  # 15 записей на страницу
    positive_page_number = request.GET.get('positive_page')
    positive_page_obj = positive_paginator.get_page(positive_page_number)

    # 2. Отрицательные корреляции с пагинацией
    negative_correlations = all_correlations.filter(
        correlation_score__lt=-0.5
    ).order_by('correlation_score')

    negative_paginator = Paginator(negative_correlations, 15)
    negative_page_number = request.GET.get('negative_page')
    negative_page_obj = negative_paginator.get_page(negative_page_number)

    # 3. Нейтральные/слабые корреляции (опционально, для полноты)
    neutral_correlations = all_correlations.filter(
        correlation_score__gte=-0.5,
        correlation_score__lte=0.5
    ).order_by('-occurrence_count')  # Сортировка по частоте упоминаний

    neutral_paginator = Paginator(neutral_correlations, 10)
    neutral_page_number = request.GET.get('neutral_page')
    neutral_page_obj = neutral_paginator.get_page(neutral_page_number)

    # Создаем графики
    timeline_chart = create_mood_timeline_chart(entries)
    weekday_chart = create_weekday_chart(entries)
    distribution_chart = create_mood_distribution_chart(entries)

    # Статистика
    stats = calculate_statistics(request.user)

    # Дни недели
    weekdays_ru = {
        0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
        4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
    }

    context = {
        # Пагинированные данные
        'positive_page_obj': positive_page_obj,
        'negative_page_obj': negative_page_obj,
        'neutral_page_obj': neutral_page_obj,

        # Общая статистика
        'all_correlations_count': all_correlations.count(),
        'positive_count': positive_correlations.count(),
        'negative_count': negative_correlations.count(),
        'neutral_count': neutral_correlations.count(),

        # Графики
        'timeline_chart': timeline_chart,
        'weekday_chart': weekday_chart,
        'distribution_chart': distribution_chart,

        # Статистика
        'stats': stats,
        'total_entries': entries.count(),

        # Дни недели
        'best_day_name': weekdays_ru.get(stats['best_day'], 'Недостаточно данных')
        if stats['best_day'] is not None else 'Недостаточно данных',
        'worst_day_name': weekdays_ru.get(stats['worst_day'], 'Недостаточно данных')
        if stats['worst_day'] is not None else 'Недостаточно данных',

        # Флаги для отображения разделов
        'show_neutral': request.GET.get('show_neutral', False),
    }

    return render(request, 'diary/analytics.html', context)

