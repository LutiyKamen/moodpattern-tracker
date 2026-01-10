import pandas as pd
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Q
from django.utils import timezone


def create_mood_timeline_chart(entries):
    """Создает график изменения настроения во времени"""
    if entries.count() < 2:
        return None

    data = []
    for entry in entries:
        if entry.mood_score is not None:
            data.append({
                'date': entry.date_created,
                'mood_score': entry.mood_score,
                'mood_tag': entry.get_user_mood_tag_display(),
                'word_count': entry.word_count
            })

    if not data:
        return None

    df = pd.DataFrame(data)

    # Сортируем по дате
    df = df.sort_values('date')

    # Создаем скользящее среднее для сглаживания
    df['mood_ma'] = df['mood_score'].rolling(window=3, min_periods=1).mean()

    fig = go.Figure()

    # Основная линия (сглаженная)
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['mood_ma'],
        mode='lines',
        name='Настроение (сглаженное)',
        line=dict(color='#6c7b7d', width=3),
        hovertemplate='%{x|%d.%m.%Y}<br>Настроение: %{y:.2f}<extra></extra>'
    ))

    # Точки (фактические значения)
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['mood_score'],
        mode='markers',
        name='Фактическое',
        marker=dict(
            size=8,
            color=df['mood_score'],
            colorscale='RdYlGn',
            cmin=-1,
            cmax=1,
            showscale=False,
            line=dict(width=1, color='white')
        ),
        hovertemplate='%{x|%d.%m.%Y %H:%M}<br>Настроение: %{y:.2f}<extra></extra>'
    ))

    # Линия нуля
    fig.add_hline(y=0, line_dash="dash", line_color="#d4c9be", opacity=0.5)

    fig.update_layout(
        title='',
        height=400,
        margin=dict(l=20, r=20, t=10, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='#3c2f2f'),
        showlegend=False,
        xaxis_title="Дата",
        yaxis_title="Настроение",
        yaxis_range=[-1.1, 1.1]
    )

    return pio.to_html(fig, full_html=False, config={'displayModeBar': False})


def create_weekday_chart(entries):
    """Создает график настроения по дням недели"""
    if entries.count() < 5:
        return None

    # Словарь для дней недели
    weekdays_ru = {
        0: 'Понедельник',
        1: 'Вторник',
        2: 'Среда',
        3: 'Четверг',
        4: 'Пятница',
        5: 'Суббота',
        6: 'Воскресенье'
    }

    data = []
    for entry in entries:
        if entry.mood_score is not None:
            weekday_num = entry.date_created.weekday()
            data.append({
                'weekday': weekday_num,
                'weekday_name': weekdays_ru.get(weekday_num, 'Неизвестно'),
                'mood_score': entry.mood_score
            })

    if not data:
        return None

    df = pd.DataFrame(data)

    # Группируем по дням недели
    mood_by_day = df.groupby(['weekday', 'weekday_name'])['mood_score'].agg(['mean', 'count']).reset_index()
    mood_by_day = mood_by_day.sort_values('weekday')

    # Порядок дней недели
    day_order = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    mood_by_day['weekday_name'] = pd.Categorical(mood_by_day['weekday_name'], categories=day_order, ordered=True)
    mood_by_day = mood_by_day.sort_values('weekday_name')

    # Цвета в зависимости от значения
    colors = []
    for val in mood_by_day['mean']:
        if val > 0.3:
            colors.append('#a8b8a5')  # sage
        elif val > 0:
            colors.append('#b8c9b5')  # светлый sage
        elif val > -0.3:
            colors.append('#d4c9be')  # taupe
        else:
            colors.append('#8b6b4f')  # clay

    fig = go.Figure(data=[
        go.Bar(
            x=mood_by_day['weekday_name'],
            y=mood_by_day['mean'],
            marker_color=colors,
            text=[f'{val:.2f}' for val in mood_by_day['mean']],
            textposition='outside',
            hovertemplate='%{x}<br>Среднее настроение: %{y:.2f}<br>Записей: %{customdata}<extra></extra>',
            customdata=mood_by_day['count']
        )
    ])

    fig.update_layout(
        title='',
        height=400,
        margin=dict(l=20, r=20, t=10, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='#3c2f2f'),
        showlegend=False,
        xaxis_title="День недели",
        yaxis_title="Среднее настроение",
        yaxis_range=[-1.1, 1.1]
    )

    return pio.to_html(fig, full_html=False, config={'displayModeBar': False})


def create_mood_distribution_chart(entries):
    """Создает распределение настроений по меткам"""
    if entries.count() < 3:
        return None

    mood_counts = entries.values('user_mood_tag').annotate(
        count=Count('id'),
        avg_mood=Avg('mood_score')
    ).order_by('user_mood_tag')

    if not mood_counts:
        return None

    # Названия меток
    mood_names = {
        'excellent': 'Отличное',
        'good': 'Хорошее',
        'neutral': 'Нейтральное',
        'bad': 'Плохое',
        'terrible': 'Ужасное'
    }

    data = []
    for item in mood_counts:
        data.append({
            'mood': mood_names.get(item['user_mood_tag'], item['user_mood_tag']),
            'count': item['count'],
            'avg_mood': item['avg_mood'] or 0
        })

    df = pd.DataFrame(data)

    # Цвета в соответствии с дизайном
    color_map = {
        'Отличное': '#a8b8a5',
        'Хорошее': '#b8c9b5',
        'Нейтральное': '#d4c9be',
        'Плохое': '#c9b8a5',
        'Ужасное': '#8b6b4f'
    }

    colors = [color_map.get(mood, '#6c7b7d') for mood in df['mood']]

    fig = go.Figure(data=[
        go.Bar(
            x=df['mood'],
            y=df['count'],
            marker_color=colors,
            text=df['count'],
            textposition='auto',
            hovertemplate='%{x}<br>Количество: %{y}<br>Средняя оценка: %{customdata:.2f}<extra></extra>',
            customdata=df['avg_mood']
        )
    ])

    fig.update_layout(
        title='',
        height=350,
        margin=dict(l=20, r=20, t=10, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='#3c2f2f'),
        showlegend=False,
        xaxis_title="Метка настроения",
        yaxis_title="Количество записей"
    )

    return pio.to_html(fig, full_html=False, config={'displayModeBar': False})


def calculate_statistics(user):
    """Рассчитывает общую статистику пользователя"""
    entries = DiaryEntry.objects.filter(user=user)
    correlations = MoodCorrelation.objects.filter(user=user)

    # Базовая статистика
    total_entries = entries.count()

    # Записи с оценкой настроения
    entries_with_score = entries.exclude(mood_score__isnull=True)

    if entries_with_score.exists():
        mood_stats = entries_with_score.aggregate(
            avg_mood=Avg('mood_score'),
            max_mood=Max('mood_score'),
            min_mood=Min('mood_score')
        )
        avg_mood = mood_stats['avg_mood'] or 0
        max_mood = mood_stats['max_mood'] or 0
        min_mood = mood_stats['min_mood'] or 0
    else:
        avg_mood = max_mood = min_mood = 0

    # Статистика по дням недели
    if entries_with_score.count() >= 7:
        weekday_stats = {}
        for entry in entries_with_score:
            weekday = entry.date_created.weekday()
            if weekday not in weekday_stats:
                weekday_stats[weekday] = []
            weekday_stats[weekday].append(entry.mood_score)

        # Находим лучший и худший день
        best_day = None
        worst_day = None
        best_avg = -2
        worst_avg = 2

        for weekday, scores in weekday_stats.items():
            avg = sum(scores) / len(scores)
            if avg > best_avg:
                best_avg = avg
                best_day = weekday
            if avg < worst_avg:
                worst_avg = avg
                worst_day = weekday
    else:
        best_day = worst_day = None

    # Статистика корреляций
    positive_correlations = correlations.filter(correlation_score__gt=0.05)
    negative_correlations = correlations.filter(correlation_score__lt=-0.05)

    # Самые сильные триггеры
    strongest_positive = positive_correlations.order_by('-correlation_score').first()
    strongest_negative = negative_correlations.order_by('correlation_score').first()

    # Частота ведения дневника
    if total_entries > 1:
        first_entry = entries.order_by('date_created').first()
        last_entry = entries.order_by('-date_created').first()

        if first_entry and last_entry:
            days_diff = (last_entry.date_created - first_entry.date_created).days
            if days_diff > 0:
                entries_per_day = total_entries / days_diff
            else:
                entries_per_day = total_entries
        else:
            entries_per_day = 0
    else:
        entries_per_day = 0

    return {
        'total_entries': total_entries,
        'avg_mood': avg_mood,
        'max_mood': max_mood,
        'min_mood': min_mood,
        'positive_triggers_count': positive_correlations.count(),
        'negative_triggers_count': negative_correlations.count(),
        'strongest_positive': strongest_positive,
        'strongest_negative': strongest_negative,
        'entries_per_day': round(entries_per_day, 2),
        'best_day': best_day,
        'worst_day': worst_day,
        'best_day_avg': best_avg if best_day is not None else 0,
        'worst_day_avg': worst_avg if worst_day is not None else 0,
    }


from django.db.models import Max, Min