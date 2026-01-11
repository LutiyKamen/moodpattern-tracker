web: gunicorn moodpattern_tracker.wsgi --log-file -
release: python manage.py migrate --no-input && python manage.py collectstatic --noinput