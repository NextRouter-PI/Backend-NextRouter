from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from core.views import (
    AccessibilityViewSet,
    Account_Recovery_CodeViewSet,
    Company_Admin_PermissionViewSet,
    Company_AdminViewSet,
    Company_ProfileViewSet,
    Company_Registration_RequestViewSet,
    CompanyViewSet,
    Confirmed_PassengerViewSet,
    Contract_RequestViewSet,
    Driver_Job_OpeningViewSet,
    DriverViewSet,
    Lost_ItemViewSet,
    PassengerViewSet,
    ProfileViewSet,
    Register_LinkViewSet,
    Route_GroupViewSet,
    RouteViewSet,
    System_AdminViewSet,
    UserViewSet,
)

router = DefaultRouter()

router.register(r'usuarios', UserViewSet, basename='usuarios')
router.register(r'perfis', ProfileViewSet, basename='perfis')
router.register(r'empresas', CompanyViewSet, basename='empresas')
router.register(r'perfis_empresa', Company_ProfileViewSet, basename='perfis de empresa')
router.register(r'acessibilidades', AccessibilityViewSet, basename='acessibilidades')
router.register(r'permissoes_admin_empresa', Company_Admin_PermissionViewSet, basename='permissoes de admin de empresa')
router.register(r'admins_empresa', Company_AdminViewSet, basename='admins de empresa')
router.register(r'admins_sistema', System_AdminViewSet, basename='admins de sistema')
router.register(
    r'solicitacoes_cadastro_empresa',
    Company_Registration_RequestViewSet,
    basename='solicitacoes de cadastro de empresa',
)
router.register(r'solicitacoes_contrato', Contract_RequestViewSet, basename='solicitacoes de contrato')
router.register(r'links_cadastro', Register_LinkViewSet, basename='links de cadastro')
router.register(r'motoristas', DriverViewSet, basename='motoristas')
router.register(r'passageiros', PassengerViewSet, basename='passageiros')
router.register(r'grupos_de_rotas', Route_GroupViewSet, basename='grupos de rotas')
router.register(r'rotas', RouteViewSet, basename='rotas')
router.register(r'passageiros_confirmados', Confirmed_PassengerViewSet, basename='passageiros confirmados')
router.register(r'itens_perdidos', Lost_ItemViewSet, basename='itens perdidos')
router.register(r'vagas_de_trabalho_motorista', Driver_Job_OpeningViewSet, basename='vagas de trabalho para motorista')
router.register(r'codigos_recuperacao_conta', Account_Recovery_CodeViewSet, basename='codigos de recuperacao de conta')

urlpatterns = [
    path('admin/', admin.site.urls),
    # OpenAPI 3
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/swagger/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),
    # API
    path('api/', include(router.urls)),
]
