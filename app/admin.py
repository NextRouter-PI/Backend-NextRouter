from django.contrib.admin import AdminSite


class NextRouterAdminSite(AdminSite):
    site_header = 'NextRouter — Administração'
    site_title = 'NextRouter'
    index_title = 'Gestão da plataforma'

    def get_app_list(self, request, app_label=None):
        apps = super().get_app_list(request, app_label)
        order = {'authenticator': 0, 'organizations': 1, 'router': 2, 'uploader': 3, 'auth': 4}
        return sorted(apps, key=lambda app: (order.get(app['app_label'], 5), app['name']))
