from django.apps import AppConfig


class TransportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.transport'
    label = 'router'
    verbose_name = 'Transporte e viagens'

    def ready(self):
        from modules.accounts.hooks import register_deactivation_guard
        from modules.organizations.hooks import (
            register_authorization_cloner,
            register_company_moderation_guard,
            register_membership_notifier,
            register_profile_change_guard,
            register_route_group_change_listener,
        )
        from modules.transport.admin_commands import register_cross_module_admin_commands
        from modules.transport.services.calendar import regenerate_future_days
        from modules.transport.services.configuration import clone_service_authorizations
        from modules.transport.services.governance_guards import (
            guard_company_moderation_in_transport,
            guard_profile_can_change_in_transport,
            guard_transport_deactivation,
        )
        from modules.transport.services.notifications import emit_membership_notification_in_transport

        register_deactivation_guard(guard_transport_deactivation)
        register_company_moderation_guard(guard_company_moderation_in_transport)
        register_profile_change_guard(guard_profile_can_change_in_transport)
        register_membership_notifier(emit_membership_notification_in_transport)
        register_route_group_change_listener(regenerate_future_days)
        register_authorization_cloner(clone_service_authorizations)
        register_cross_module_admin_commands()
