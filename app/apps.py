from django.contrib.admin.apps import AdminConfig


class NextRouterAdminConfig(AdminConfig):
    default_site = 'app.admin.NextRouterAdminSite'
