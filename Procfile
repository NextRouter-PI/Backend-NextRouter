web: env DJANGO_SETTINGS_MODULE=app.settings.prod daphne -b 0.0.0.0 -p $PORT app.asgi:application
worker: env DJANGO_SETTINGS_MODULE=app.settings.prod python manage.py process_route_jobs
release: env DJANGO_SETTINGS_MODULE=app.settings.prod python manage.py migrate --noinput
