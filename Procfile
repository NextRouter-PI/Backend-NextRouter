web: daphne -b 0.0.0.0 -p $PORT app.asgi:application
release: python manage.py migrate --noinput && python manage.py create_admin && python manage.py seed_demo_data
