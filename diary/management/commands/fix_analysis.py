from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from diary.analysis_utils import recalculate_correlations


class Command(BaseCommand):
    help = 'Пересчитывает корреляции для пользователей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Имя пользователя'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Все пользователи'
        )

    def handle(self, *args, **options):
        if options['all']:
            users = User.objects.all()
            for user in users:
                count = recalculate_correlations(user)
                self.stdout.write(f'{user.username}: {count} корреляций')
            self.stdout.write(self.style.SUCCESS('Готово!'))

        elif options['username']:
            try:
                user = User.objects.get(username=options['username'])
                count = recalculate_correlations(user)
                self.stdout.write(
                    self.style.SUCCESS(f'{user.username}: {count} корреляций')
                )
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR('Пользователь не найден'))

        else:
            self.stdout.write('Используйте: --username ИМЯ или --all')