from django.apps import AppConfig


class TransportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.transport'
    label = 'router'
    verbose_name = 'Transporte e viagens'

    def ready(self):
        from modules.transport import signals  # ruff: ignore[unused-import]
