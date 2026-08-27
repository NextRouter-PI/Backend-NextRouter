web: gunicorn app.wsgi --log-file -
release: python manage.py migrate --noinput && python manage.py create_admin
