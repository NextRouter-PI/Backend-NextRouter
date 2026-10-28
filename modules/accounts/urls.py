from django.urls import path
from rest_framework.routers import SimpleRouter

from .api.views.auth import (
    CsrfView,
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    DeactivateSelfView,
    RevokeAllSessionsView,
    UserSessionDeactivateView,
    UserSessionsView,
)
from .api.views.email_change import EmailChangeViewSet
from .api.views.email_token import EmailTokenViewSet
from .api.views.registration import PasswordResetTokenViewSet, RegistrationTokenViewSet
from .api.views.user import UserViewSet

router = SimpleRouter()
router.register('email-tokens', EmailTokenViewSet, basename='email-tokens')
router.register('users', UserViewSet, basename='users')

urlpatterns = [
    path('csrf/', CsrfView.as_view(), name='csrf'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='refresh'),
    path('me/logout/', CustomLogoutView.as_view(), name='logout'),
    path('me/deactivate/', DeactivateSelfView.as_view(), name='deactivate-self'),
    path('me/revoke-sessions/', RevokeAllSessionsView.as_view(), name='revoke-sessions'),
    path('sessions/', UserSessionsView.as_view(), name='user-sessions-list'),
    path('sessions/<uuid:session_id>/', UserSessionDeactivateView.as_view(), name='user-sessions-deactivate'),
    path('registration/request/', RegistrationTokenViewSet.as_view({'post': 'create_token'})),
    path('registration/verify/', RegistrationTokenViewSet.as_view({'post': 'verify_token'})),
    path('password-reset/request/', PasswordResetTokenViewSet.as_view({'post': 'create_token'})),
    path('password-reset/verify/', PasswordResetTokenViewSet.as_view({'post': 'verify_token'})),
    path('password-reset/confirm/', PasswordResetTokenViewSet.as_view({'post': 'reset_password'})),
    path('email-change/request/', EmailChangeViewSet.as_view({'post': 'create_token'})),
    path('email-change/verify/', EmailChangeViewSet.as_view({'post': 'verify_token'})),
    path('email-change/confirm/', EmailChangeViewSet.as_view({'post': 'confirm'})),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('token/logout/', CustomLogoutView.as_view(), name='token_logout'),
]
