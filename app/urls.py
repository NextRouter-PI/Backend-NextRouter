from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.utils import extend_schema, extend_schema_view
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


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
    path('admin/', admin.site.urls),
    path('api/schema/', NextRouterSchemaView.as_view(), name='schema'),
    path('api/doc/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/', include('app.api')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_ENDPOINT, document_root=settings.MEDIA_ROOT)
