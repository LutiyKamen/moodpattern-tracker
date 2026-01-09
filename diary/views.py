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

    # Статистика
    total_entries = entries.count()
    avg_mood = entries.aggregate(avg=Avg('mood_score'))['avg'] or 0

    # Топ-триггеры
    top_correlations = MoodCorrelation.objects.filter(
        user=request.user
    ).exclude(
        occurrence_count__lt=3  # Исключаем редкие слова
    ).order_by('-correlation_score')[:5]

    # График настроения за последние 7 дней
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_entries = entries.filter(date_created__gte=seven_days_ago)

    mood_chart_html = None
    if recent_entries.count() > 1:
        # Создаём DataFrame для Plotly
        df = pd.DataFrame(list(recent_entries.values('date_created', 'mood_score')))
        df['date'] = pd.to_datetime(df['date_created']).dt.date

        # Группируем по дате
        daily_avg = df.groupby('date')['mood_score'].mean().reset_index()

        # Создаём график
        fig = px.line(
            daily_avg,
            x='date',
            y='mood_score',
            title='Динамика настроения за 7 дней',
            labels={'date': 'Дата', 'mood_score': 'Настроение'},
            markers=True
        )

        # Настраиваем график
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode='x unified'
        )

        fig.update_traces(
            line=dict(color='#4e73df', width=3),
            marker=dict(size=8, color='#4e73df')
        )

        # Конвертируем в HTML
        mood_chart_html = pio.to_html(fig, full_html=False, config={'displayModeBar': False})

    context = {
        'page_obj': page_obj,
        'total_entries': total_entries,
        'avg_mood': avg_mood,
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
    # Получаем ВСЕ корреляции пользователя
    all_correlations = MoodCorrelation.objects.filter(user=request.user)

    # Считаем общее количество
    all_correlations_count = all_correlations.count()

    # Разделяем на позитивные и негативные с либеральными порогами
    positive_correlations = all_correlations.filter(
        correlation_score__gt=0.05
    ).order_by('-correlation_score')

    negative_correlations = all_correlations.filter(
        correlation_score__lt=-0.05
    ).order_by('correlation_score')  # От самых негативных

    # Если мало данных, показываем топ корреляций по абсолютному значению
    if all_correlations_count > 0 and all_correlations_count < 10:
        # Создаем список для ручной сортировки
        correlations_list = list(all_correlations)
        # Сортируем по абсолютному значению корреляции
        correlations_list.sort(key=lambda x: abs(x.correlation_score), reverse=True)

        # Если мало позитивных/негативных, показываем топ из всех
        if positive_correlations.count() < 3:
            # Берем топ-5 позитивных по абсолютному значению
            top_positive = [c for c in correlations_list if c.correlation_score > 0][:5]
            if top_positive:
                positive_correlations = top_positive

        if negative_correlations.count() < 3:
            # Берем топ-5 негативных по абсолютному значению
            top_negative = [c for c in correlations_list if c.correlation_score < 0][:5]
            if top_negative:
                negative_correlations = top_negative

    # Статистика по дням недели
    entries = DiaryEntry.objects.filter(user=request.user)

    day_chart_html = None
    if entries.count() >= 3:  # Минимум 3 записи для графика
        try:
            # Создаём DataFrame для анализа дней недели
            import pandas as pd
            import plotly.express as px
            import plotly.io as pio

            # Словарь для перевода дней недели
            days_mapping = {
                0: 'Понедельник',
                1: 'Вторник',
                2: 'Среда',
                3: 'Четверг',
                4: 'Пятница',
                5: 'Суббота',
                6: 'Воскресенье'
            }

            # Собираем данные
            data = []
            for entry in entries:
                if entry.date_created and entry.mood_score is not None:
                    day_num = entry.date_created.weekday()  # 0=понедельник, 6=воскресенье
                    data.append({
                        'day_num': day_num,
                        'day_name': days_mapping.get(day_num, 'Неизвестно'),
                        'mood_score': entry.mood_score,
                        'date': entry.date_created.date()
                    })

            if data:
                df = pd.DataFrame(data)

                # Группируем по дням недели и считаем среднее
                mood_by_day = df.groupby(['day_num', 'day_name'])['mood_score'].mean().reset_index()
                mood_by_day = mood_by_day.sort_values('day_num')

                # Создаём график
                fig = px.bar(
                    mood_by_day,
                    x='day_name',
                    y='mood_score',
                    title='Среднее настроение по дням недели',
                    labels={'day_name': 'День недели', 'mood_score': 'Среднее настроение'},
                    color='mood_score',
                    color_continuous_scale='RdYlGn',
                    text=mood_by_day['mood_score'].round(2)
                )

                fig.update_traces(
                    texttemplate='%{text:.2f}',
                    textposition='outside',
                    marker_line_width=0
                )

                fig.update_layout(
                    height=400,
                    margin=dict(l=20, r=20, t=40, b=20),
                    coloraxis_showscale=False,
                    showlegend=False,
                    yaxis_range=[-1, 1]  # Фиксируем диапазон для настроения
                )

                day_chart_html = pio.to_html(fig, full_html=False, config={'displayModeBar': False})

        except Exception as e:
            print(f"Ошибка создания графика дней недели: {e}")
            day_chart_html = None

    context = {
        'all_correlations_count': all_correlations_count,
        'positive_correlations': positive_correlations,
        'negative_correlations': negative_correlations,
        'day_chart_html': day_chart_html,
        'total_entries': entries.count(),
    }

    return render(request, 'diary/analytics.html', context)