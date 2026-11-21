from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.organizations'
    verbose_name = 'Empresas e vínculos'

    def ready(self):
        from modules.accounts.hooks import register_deactivation_pre_lock
        from modules.organizations.access import can_access_organization_document, lock_user_companies
        from modules.uploads.access import register_document_access_checker

        register_deactivation_pre_lock(lock_user_companies)
        register_document_access_checker(can_access_organization_document)
