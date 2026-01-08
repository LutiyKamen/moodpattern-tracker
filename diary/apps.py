from django.apps import AppConfig  # ← ДОБАВЬТЕ ЭТУ СТРОКУ!


class DiaryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'diary'

    def ready(self):
        print("=== DiaryConfig.ready() вызван ===")
        # Импортируем сигналы
        import diary.signals
        print("=== Сигналы импортированы ===")