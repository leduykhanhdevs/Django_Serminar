#!/usr/bin/env sh
set -eu

command_name="${1:-web}"

case "$command_name" in
  migrate)
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    ;;
  web)
    python manage.py collectstatic --noinput
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -
    ;;
  worker)
    exec celery -A config worker --loglevel=INFO
    ;;
  beat)
    exec celery -A config beat --loglevel=INFO
    ;;
  *)
    exec "$@"
    ;;
esac

