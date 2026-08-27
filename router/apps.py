from django.apps import AppConfig


class RouterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'router'

    def ready(self):
        from router import signals  # noqa: F401
