web: gunicorn moodpattern_tracker.wsgi --log-file -
release:
  python manage.py makemigrations --noinput &&
  python manage.py migrate --noinput &&
  python manage.py collectstatic --noinput