from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.accounts'
    # O label mantém o AUTH_USER_MODEL e o histórico de migrações existentes.
    label = 'authenticator'
    verbose_name = 'Contas e autenticação'
