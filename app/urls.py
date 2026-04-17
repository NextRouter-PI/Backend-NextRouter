from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenRefreshView,
)

from core.views import (
    CompanyViewSet,
    DriverViewSet,
    PassengerViewSet,
    UserViewSet,
)

router = DefaultRouter()

router.register(
    r"usuarios",
    UserViewSet,
    basename="usuarios"
)

router.register(
    r"empresas",
    CompanyViewSet,
    basename="empresas"
)

router.register(
    r"motoristas",
    DriverViewSet,
    basename="motoristas"
)

router.register(
    r"passageiros",
    PassengerViewSet,
    basename="passageiros"
)

urlpatterns = [

    path(
        "admin/",
        admin.site.urls
    ),

    path(
        "api/auth/login/",
        UserViewSet.as_view({
            "post": "login"
        }),
        name="login"
    ),

    path(
        "api/auth/register/passageiro/",
        UserViewSet.as_view({
            "post": "register_passenger"
        }),
        name="register_passenger"
    ),

    path(
        "api/auth/register/motorista/",
        UserViewSet.as_view({
            "post": "register_driver"
        }),
        name="register_driver"
    ),

    path(
        "api/auth/me/",
        UserViewSet.as_view({
            "get": "me"
        }),
        name="me"
    ),

    path(
        "api/auth/status-motorista/",
        UserViewSet.as_view({
            "get": "status_motorista"
        }),
        name="status_motorista"
    ),

    path(
        "api/auth/refresh/",
        TokenRefreshView.as_view(),
        name="refresh"
    ),

    path(
        "api/auth/logout/",
        TokenBlacklistView.as_view(),
        name="logout"
    ),

    path(
        "api/",
        include(router.urls)
    ),
]
