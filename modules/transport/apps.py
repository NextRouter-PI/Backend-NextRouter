from django.apps import AppConfig


class TransportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.transport'
    label = 'router'
    verbose_name = 'Transporte e viagens'

    def ready(self):
        from modules.accounts.hooks import register_deactivation_guard
        from modules.organizations.hooks import register_company_moderation_guard
        from modules.transport.admin_commands import register_cross_module_admin_commands
        from modules.transport.services.governance import (
            guard_company_moderation_in_transport,
            guard_transport_deactivation,
        )

        register_deactivation_guard(guard_transport_deactivation)
        register_company_moderation_guard(guard_company_moderation_in_transport)
        register_cross_module_admin_commands()
