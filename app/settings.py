import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# =====================================
# ENV
# =====================================
load_dotenv()

MODE = os.getenv("MODE", "DEVELOPMENT")

BASE_DIR = Path(__file__).resolve().parent.parent


# =====================================
# SECURITY
# =====================================
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-dev-key"
)

DEBUG = os.getenv(
    "DEBUG",
    "True"
) == "True"

ALLOWED_HOSTS = ["*"]


# =====================================
# FRONTEND / CORS / CSRF
# =====================================
FRONTEND_URLS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    *FRONTEND_URLS,
]

CORS_ALLOWED_ORIGINS = FRONTEND_URLS

CORS_ALLOW_CREDENTIALS = True


# =====================================
# APPS
# =====================================
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "corsheaders",
    "cloudinary",
    "cloudinary_storage",
    "django_extensions",
    "django_filters",
    "drf_spectacular",
    "rest_framework",

    # Local
    "core",
]


# =====================================
# MIDDLEWARE
# =====================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =====================================
# URLS / WSGI
# =====================================
ROOT_URLCONF = "app.urls"

WSGI_APPLICATION = "app.wsgi.application"


# =====================================
# TEMPLATES
# =====================================
TEMPLATES = [
    {
        "BACKEND":
        "django.template.backends.django.DjangoTemplates",

        "DIRS": [],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# =====================================
# DATABASE
# =====================================
DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///db.sqlite3",
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# =====================================
# PASSWORDS
# =====================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
        "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.MinimumLengthValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]


# =====================================
# INTERNATIONALIZATION
# =====================================
LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True
USE_TZ = True


# =====================================
# STATIC FILES
# =====================================
STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"


# =====================================
# MEDIA FILES
# =====================================
MEDIA_ROOT = BASE_DIR / "media"

if MODE == "DEVELOPMENT":
    MEDIA_URL = "/media/"
else:
    MEDIA_URL = "/media/"

    CLOUDINARY_URL = os.getenv(
        "CLOUDINARY_URL"
    )

    STORAGES = {
        "default": {
            "BACKEND":
            "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND":
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }


# =====================================
# DEFAULT PK
# =====================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =====================================
# CUSTOM USER
# =====================================
AUTH_USER_MODEL = "core.User"


# =====================================
# JWT
# =====================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":
        timedelta(hours=2),

    "REFRESH_TOKEN_LIFETIME":
        timedelta(days=7),

    "ROTATE_REFRESH_TOKENS":
        True,

    "BLACKLIST_AFTER_ROTATION":
        True,

    "ALGORITHM":
        "HS256",

    "SIGNING_KEY":
        SECRET_KEY,

    "AUTH_HEADER_TYPES":
        ("Bearer",),

    "USER_ID_FIELD":
        "id",

    "USER_ID_CLAIM":
        "user_id",
}


# =====================================
# DRF
# =====================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "core.authentication.TokenAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),

    "DEFAULT_PAGINATION_CLASS":
        "app.pagination.CustomPagination",

    "DEFAULT_SCHEMA_CLASS":
        "drf_spectacular.openapi.AutoSchema",

    "PAGE_SIZE":
        10,
}


# =====================================
# SWAGGER
# =====================================
SPECTACULAR_SETTINGS = {
    "TITLE": "NEXTROUTER API",
    "DESCRIPTION":
        "API principal do sistema.",
    "VERSION":
        "1.0.0",
}


# =====================================
# PASSAGE
# =====================================
PASSAGE_APP_ID = os.getenv(
    "PASSAGE_APP_ID",
    "app_id"
)

PASSAGE_API_KEY = os.getenv(
    "PASSAGE_API_KEY",
    "api_key"
)


# =====================================
# LOG
# =====================================
print(
    f"{MODE = }\n"
    f"{DEBUG = }\n"
    f"{MEDIA_URL = }\n"
    f"{DATABASES = }"
)
