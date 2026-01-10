from django.db.models import Count, Avg, Max, Min
from textblob import TextBlob
import re
from collections import Counter
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


def analyze_text_sentiment(text):
    """Анализирует тональность текста"""
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        # Коррекция для русского
        polarity = polarity * 1.2
        return max(-1.0, min(1.0, polarity))
    except:
        return 0


def extract_keywords(text):
    """Извлекает ключевые слова из текста"""
    # Русские стоп-слова
    stop_words = {
        'это', 'вот', 'какой', 'который', 'сегодня', 'завтра', 'вчера',
        'очень', 'просто', 'можно', 'нужно', 'будет', 'есть', 'был',
        'была', 'было', 'были', 'весь', 'все', 'всё', 'сам', 'сама',
        'само', 'сами', 'раз', 'два', 'три', 'год', 'года', 'лет'
    }

    # Очистка текста
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\d+', ' ', text)

    # Извлечение русских слов
    words = re.findall(r'\b[а-яё]{4,12}\b', text)

    # Фильтрация стоп-слов
    filtered = [w for w in words if w not in stop_words and len(w) >= 4]

    return filtered


def calculate_statistics(user):
    """Рассчитывает статистику пользователя"""
    from diary.models import DiaryEntry, MoodCorrelation

    entries = DiaryEntry.objects.filter(user=user)
    correlations = MoodCorrelation.objects.filter(user=user)

    # Базовая статистика
    total_entries = entries.count()

    # Статистика настроения
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

    # Статистика корреляций
    positive_count = correlations.filter(correlation_score__gt=0.05).count()
    negative_count = correlations.filter(correlation_score__lt=-0.05).count()

    # Сильнейшие триггеры
    strongest_positive = correlations.filter(
        correlation_score__gt=0.05
    ).order_by('-correlation_score').first()

    strongest_negative = correlations.filter(
        correlation_score__lt=-0.05
    ).order_by('correlation_score').first()

    return {
        'total_entries': total_entries,
        'avg_mood': avg_mood,
        'max_mood': max_mood,
        'min_mood': min_mood,
        'positive_triggers_count': positive_count,
        'negative_triggers_count': negative_count,
        'strongest_positive': strongest_positive,
        'strongest_negative': strongest_negative,
        'entries_per_day': 0,  # Упрощенно
        'best_day': None,
        'worst_day': None,
        'best_day_avg': 0,
        'worst_day_avg': 0,
    }


def create_mood_timeline_chart(entries):
    """График изменения настроения"""
    if entries.count() < 2:
        return None

    data = []
    for entry in entries:
        if entry.mood_score is not None:
            data.append({
                'date': entry.date_created,
                'mood_score': entry.mood_score,
            })

    if not data:
        return None

    df = pd.DataFrame(data)
    df = df.sort_values('date')

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['mood_score'],
        mode='lines+markers',
        line=dict(color='#6c7b7d', width=2),
        marker=dict(size=6, color=df['mood_score'],
                    colorscale='RdYlGn', cmin=-1, cmax=1),
        hovertemplate='%{x|%d.%m.%Y %H:%M}<br>Настроение: %{y:.2f}<extra></extra>'
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="#d4c9be", opacity=0.5)

    fig.update_layout(
        height=350,
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
    """График по дням недели"""
    if entries.count() < 5:
        return None

    weekdays_ru = {
        0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт',
        4: 'Пт', 5: 'Сб', 6: 'Вс'
    }

    data = []
    for entry in entries:
        if entry.mood_score is not None:
            weekday = entry.date_created.weekday()
            data.append({
                'weekday': weekday,
                'weekday_name': weekdays_ru.get(weekday, '?'),
                'mood_score': entry.mood_score
            })

    if not data:
        return None

    df = pd.DataFrame(data)
    mood_by_day = df.groupby(['weekday', 'weekday_name'])['mood_score'].mean().reset_index()
    mood_by_day = mood_by_day.sort_values('weekday')

    # Цвета
    colors = []
    for val in mood_by_day['mood_score']:
        if val > 0.3:
            colors.append('#a8b8a5')
        elif val > 0:
            colors.append('#b8c9b5')
        elif val > -0.3:
            colors.append('#d4c9be')
        else:
            colors.append('#8b6b4f')

    fig = go.Figure(data=[
        go.Bar(
            x=mood_by_day['weekday_name'],
            y=mood_by_day['mood_score'],
            marker_color=colors,
            text=[f'{val:.2f}' for val in mood_by_day['mood_score']],
            textposition='outside',
        )
    ])

    fig.update_layout(
        height=350,
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
    """Распределение настроений"""
    if entries.count() < 3:
        return None

    mood_counts = entries.values('user_mood_tag').annotate(
        count=Count('id')
    ).order_by('user_mood_tag')

    if not mood_counts:
        return None

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
            'count': item['count']
        })

    df = pd.DataFrame(data)

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
        )
    ])

    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=10, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='#3c2f2f'),
        showlegend=False,
        xaxis_title="Настроение",
        yaxis_title="Количество"
    )

    return pio.to_html(fig, full_html=False, config={'displayModeBar': False})