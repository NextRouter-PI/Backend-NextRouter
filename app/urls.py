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

from authenticator.views import (
    CompanyGroupRouteViewSet,
    CompanyViewSet,
    DriverRatingViewSet,
    DriverViewSet,
    EmailTokenViewSet,
    PassengerViewSet,
    UserViewSet,
)
from authenticator.views.auth import (
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
)
from router.views import (
    CompanyRouteScheduleViewSet,
    ConfirmPassengerRouteViewSet,
    LostItemViewSet,
    PathViewSet,
    TravelViewSet,
    VehicleViewSet,
)

router = DefaultRouter()

router.register(r'passengers', PassengerViewSet, basename='passengers')
router.register(r'drivers', DriverViewSet, basename='drivers')
router.register(r'companies', CompanyViewSet, basename='companies')
router.register(r'company-route-groups', CompanyGroupRouteViewSet, basename='company-route-groups')
router.register(r'route-schedules', CompanyRouteScheduleViewSet, basename='route-schedules')
router.register(r'confirmations', ConfirmPassengerRouteViewSet, basename='confirmations')
router.register(r'lost-items', LostItemViewSet, basename='lost-items')
router.register(r'paths', PathViewSet, basename='paths')
router.register(r'vehicles', VehicleViewSet, basename='vehicles')
router.register(r'travels', TravelViewSet, basename='travels')
router.register(r'driver-ratings', DriverRatingViewSet, basename='driver-ratings')
router.register(r'email-tokens', EmailTokenViewSet, basename='email-tokens')
router.register(r'users', UserViewSet, basename='users')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/doc/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/logout/', CustomLogoutView.as_view(), name='token_logout'),
    path('api/', include(router.urls)),
    path('api/uploads/', include('uploader.router')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_ENDPOINT, document_root=settings.MEDIA_ROOT)
