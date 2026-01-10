from django.db.models import Avg, Count, Max, Min
from diary.analytics_utils import calculate_statistics  # Добавить этот импорт
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login, logout
from django.db.models import Count, Avg
from django.core.paginator import Paginator
import plotly.express as px
import plotly.io as pio
import pandas as pd
from datetime import datetime, timedelta
from .models import DiaryEntry, MoodCorrelation
from .forms import DiaryEntryForm, UserRegisterForm, UserLoginForm


def home(request):
    """Главная страница (публичная)"""
    context = {}

    # Показываем демо-статистику для гостей
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Пример аналитики для демонстрации
    context['demo_data'] = {
        'total_entries': 1250,
        'avg_mood': 0.35,
        'top_triggers': [
            {'word': 'работа', 'correlation': -0.42},
            {'word': 'друзья', 'correlation': 0.78},
            {'word': 'спорт', 'correlation': 0.65},
        ]
    }

    return render(request, 'diary/home.html', context)


def register_view(request):
    """Регистрация пользователя"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать!')
            return redirect('dashboard')
    else:
        form = UserRegisterForm()

    return render(request, 'diary/register.html', {'form': form})


def login_view(request):
    """Авторизация пользователя"""
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
    """Выход из системы"""
    logout(request)
    messages.info(request, 'Вы успешно вышли из системы.')
    return redirect('home')


@login_required
def dashboard(request):
    """Личный кабинет пользователя"""
    # Получаем записи пользователя
    entries = DiaryEntry.objects.filter(user=request.user).order_by('-date_created')

    # Пагинация
    paginator = Paginator(entries, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Статистика - ИСПРАВЛЕНО: правильный расчет среднего
    total_entries = entries.count()

    # Фильтруем записи с вычисленным mood_score
    entries_with_score = entries.exclude(mood_score__isnull=True)
    if entries_with_score.exists():
        avg_mood = entries_with_score.aggregate(Avg('mood_score'))['mood_score__avg']
    else:
        avg_mood = 0

    # Топ-триггеры - ИСПРАВЛЕНО: берем корреляции с достаточным количеством упоминаний
    top_correlations = MoodCorrelation.objects.filter(
        user=request.user,
        occurrence_count__gte=2  # Минимум 2 упоминания
    ).order_by('-correlation_score')[:5]

    # График настроения за последние 7 дней - ИСПРАВЛЕНО: правильная логика
    mood_chart_html = None
    if entries_with_score.count() > 1:
        try:
            # Создаём DataFrame для Plotly
            import pandas as pd
            import plotly.express as px
            import plotly.io as pio

            # Собираем данные за последние 7 дней
            from datetime import datetime, timedelta
            seven_days_ago = datetime.now() - timedelta(days=7)

            recent_entries = entries_with_score.filter(date_created__gte=seven_days_ago)

            if recent_entries.count() >= 2:
                data = []
                for entry in recent_entries:
                    data.append({
                        'date': entry.date_created.date(),
                        'mood_score': entry.mood_score,
                        'mood_tag': entry.get_user_mood_tag_display()
                    })

                df = pd.DataFrame(data)

                # Группируем по дате (среднее за день)
                daily_avg = df.groupby('date')['mood_score'].mean().reset_index()

                # Создаём график
                fig = px.line(
                    daily_avg,
                    x='date',
                    y='mood_score',
                    title='',
                    labels={'date': 'Дата', 'mood_score': 'Настроение'},
                    markers=True
                )

                # Настраиваем стиль в соответствии с дизайном
                fig.update_layout(
                    height=300,
                    margin=dict(l=20, r=20, t=10, b=20),
                    hovermode='x unified',
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font=dict(color='#3c2f2f')
                )

                # Цвет линии в зависимости от среднего значения
                avg_line = daily_avg['mood_score'].mean()
                line_color = '#a8b8a5' if avg_line > 0 else '#8b6b4f' if avg_line < 0 else '#6c7b7d'

                fig.update_traces(
                    line=dict(color=line_color, width=2.5),
                    marker=dict(size=6, color=line_color)
                )

                # Добавляем горизонтальную линию на 0
                fig.add_hline(y=0, line_dash="dash", line_color="#d4c9be", opacity=0.5)

                # Конвертируем в HTML
                mood_chart_html = pio.to_html(fig, full_html=False, config={'displayModeBar': False})

        except Exception as e:
            print(f"Ошибка создания графика: {e}")
            mood_chart_html = None

    context = {
        'page_obj': page_obj,
        'total_entries': total_entries,
        'avg_mood': avg_mood or 0,  # Убедимся, что не None
        'top_correlations': top_correlations,
        'mood_chart_html': mood_chart_html,
    }

    return render(request, 'diary/dashboard.html', context)


@login_required
def create_entry(request):
    """Создание новой записи"""
    if request.method == 'POST':
        form = DiaryEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            messages.success(request, 'Запись успешно добавлена! Анализ настроения выполнен.')
            return redirect('dashboard')
    else:
        form = DiaryEntryForm()

    return render(request, 'diary/entry_form.html', {'form': form, 'title': 'Новая запись'})


@login_required
def edit_entry(request, entry_id):
    """Редактирование существующей записи"""
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
    """Страница детальной аналитики"""
    from .analytics_utils import (
        create_mood_timeline_chart,
        create_weekday_chart,
        create_mood_distribution_chart,
        calculate_statistics
    )

    # Получаем все записи пользователя
    entries = DiaryEntry.objects.filter(user=request.user)

    # Получаем все корреляции пользователя
    all_correlations = MoodCorrelation.objects.filter(user=request.user)
    all_correlations_count = all_correlations.count()

    # Разделяем на позитивные и негативные с правильными порогами
    positive_correlations = all_correlations.filter(
        correlation_score__gt=0.05,
        occurrence_count__gte=2  # Минимум 2 упоминания
    ).order_by('-correlation_score')

    negative_correlations = all_correlations.filter(
        correlation_score__lt=-0.05,
        occurrence_count__gte=2  # Минимум 2 упоминания
    ).order_by('correlation_score')

    # Создаем графики
    timeline_chart = create_mood_timeline_chart(entries)
    weekday_chart = create_weekday_chart(entries)
    distribution_chart = create_mood_distribution_chart(entries)

    # Рассчитываем статистику
    stats = calculate_statistics(request.user)

    # Названия дней недели для отображения
    weekdays_ru = {
        0: 'Понедельник',
        1: 'Вторник',
        2: 'Среда',
        3: 'Четверг',
        4: 'Пятница',
        5: 'Суббота',
        6: 'Воскресенье'
    }

    context = {
        'all_correlations_count': all_correlations_count,
        'positive_correlations': positive_correlations,
        'negative_correlations': negative_correlations,
        'timeline_chart': timeline_chart,
        'weekday_chart': weekday_chart,
        'distribution_chart': distribution_chart,
        'stats': stats,
        'total_entries': entries.count(),
        'best_day_name': weekdays_ru.get(stats['best_day'], 'Недостаточно данных') if stats[
                                                                                          'best_day'] is not None else 'Недостаточно данных',
        'worst_day_name': weekdays_ru.get(stats['worst_day'], 'Недостаточно данных') if stats[
                                                                                            'worst_day'] is not None else 'Недостаточно данных',
    }

    return render(request, 'diary/analytics.html', context)