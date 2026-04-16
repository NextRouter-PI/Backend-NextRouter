# projeto/urls.py

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

    # ADMIN
    path(
        "admin/",
        admin.site.urls
    ),

    # =========================
    # AUTH
    # =========================

    # LOGIN
    path(
        "api/auth/login/",
        UserViewSet.as_view({
            "post": "login"
        }),
        name="login"
    ),

    # REGISTER
    path(
        "api/auth/register/",
        UserViewSet.as_view({
            "post": "register"
        }),
        name="register"
    ),

    # USUARIO LOGADO
    path(
        "api/auth/me/",
        UserViewSet.as_view({
            "get": "me"
        }),
        name="me"
    ),

    # REFRESH TOKEN
    path(
        "api/auth/refresh/",
        TokenRefreshView.as_view(),
        name="refresh"
    ),

    # LOGOUT
    path(
        "api/auth/logout/",
        TokenBlacklistView.as_view(),
        name="logout"
    ),

    # =========================
    # CRUD API
    # =========================
    path(
        "api/",
        include(router.urls)
    ),
]
