from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from core.views import (
    EmpresaViewSet,
    MotoristaViewSet,
    PassageiroViewSet,
    RegistroEmpresaView,
    RegistroMotoristaView,
    RegistroPassageiroView,
    UserRegistrationView,
    UserViewSet,
)

router = DefaultRouter()
router.register(r'usuarios', UserViewSet, basename='usuarios')
router.register(r'passageiros', PassageiroViewSet, basename='passageiros')
router.register(r'motoristas', MotoristaViewSet, basename='motoristas')
router.register(r'empresas', EmpresaViewSet, basename='empresas')

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    path(
        'api/doc/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),

    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),

    path(
        'api/token/',
        TokenObtainPairView.as_view(),
        name='token_obtain_pair'
    ),

    path(
        'api/token/refresh/',
        TokenRefreshView.as_view(),
        name='token_refresh'
    ),

    path(
        'api/token/verify/',
        TokenVerifyView.as_view(),
        name='token_verify'
    ),

    path(
        'api/registro/',
        UserRegistrationView.as_view(),
        name='user_registration'
    ),

    path(
        'api/registro/passageiro/',
        RegistroPassageiroView.as_view(),
        name='registro_passageiro'
    ),

    path(
        'api/registro/motorista/',
        RegistroMotoristaView.as_view(),
        name='registro_motorista'
    ),

    path(
        'api/registro/empresa/',
        RegistroEmpresaView.as_view(),
        name='registro_empresa'
    ),

    path('api/', include(router.urls)),
]
