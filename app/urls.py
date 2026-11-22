from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.utils import extend_schema, extend_schema_view
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from app.frontend import (
    favicon,
    frontend,
    pwa_icon,
    pwa_manifest,
    pwa_register_sw,
    pwa_service_worker,
    pwa_workbox,
)
from app.health import live, ready
from app.html_templates import html_template


@extend_schema_view(
    get=extend_schema(
        tags=['Documentação'],
        summary='Consulte o schema OpenAPI',
        description='Público. Retorna o contrato OpenAPI gerado para a API.',
    )
)
class NextRouterSchemaView(SpectacularAPIView):
    pass


urlpatterns = [
    path('html-template-test/', html_template, name='html-template-index'),
    path('html-template-test/<path:filename>', html_template, name='html-template-file'),
    path('health/live/', live, name='health-live'),
    path('health/ready/', ready, name='health-ready'),
    path('admin/', admin.site.urls),
    path('api/schema/', NextRouterSchemaView.as_view(), name='schema'),
    path('api/doc/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/', include('app.api')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_ENDPOINT, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    path('favicon.ico', favicon),
    path('manifest.webmanifest', pwa_manifest),
    path('sw.js', pwa_service_worker),
    path('registerSW.js', pwa_register_sw),
    re_path(r'^(?P<filename>workbox-[0-9a-f]{8}\.js)$', pwa_workbox),
    re_path(r'^icons/(?P<filename>[^/]+)$', pwa_icon),
    re_path(r'^(?P<route>.*)$', frontend),
]

handler404 = 'app.frontend.not_found'
