from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from core.views import (
    CompanyGroupRouteViewSet,
    CompanyViewSet,
    DriverViewSet,
    PassengerViewSet,
    UserViewSet,
)
from core.views.auth import (
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
)
from uploader.router import router as uploader_router

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'passengers', PassengerViewSet, basename='passengers')
router.register(r'drivers', DriverViewSet, basename='drivers')
router.register(r'companies', CompanyViewSet, basename='companies')
router.register(r'companies-route-groups', CompanyGroupRouteViewSet, basename='companies route groups')

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
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/logout/', CustomLogoutView.as_view(), name='token_logout'),
    path('api/', include(router.urls)),
    path('api/media/', include(uploader_router.urls)),
]

urlpatterns += static(settings.MEDIA_ENDPOINT, document_root=settings.MEDIA_ROOT)
