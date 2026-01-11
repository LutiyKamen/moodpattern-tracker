from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import DiaryEntry


class UserRegisterForm(UserCreationForm):
    """Форма регистрации пользователя"""
    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Введите email'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите имя пользователя'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем Bootstrap классы ко всем полям
        for field_name in self.fields:
            if field_name not in ['username', 'email']:  # Эти уже настроены
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        """Валидация email"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Этот email уже используется')
        return email


class UserLoginForm(AuthenticationForm):
    """Форма авторизации пользователя"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем Bootstrap классы
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Имя пользователя'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Пароль'})


class DiaryEntryForm(forms.ModelForm):
    """Форма для создания/редактирования дневниковой записи"""

    class Meta:
        model = DiaryEntry
        fields = ['text', 'user_mood_tag']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Опишите свой день, мысли, события...'
            }),
            'user_mood_tag': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'text': 'Текст записи',
            'user_mood_tag': 'Ваше настроение',
        }
        help_texts = {
            'text': 'Чем подробнее вы опишете день, тем точнее будет анализ.',
        }

    def clean_text(self):
        """Валидация текста записи"""
        text = self.cleaned_data.get('text')
        if len(text.strip()) < 10:
            raise forms.ValidationError('Запись должна содержать минимум 10 символов')
        return text