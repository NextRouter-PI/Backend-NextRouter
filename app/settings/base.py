import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Constrói o caminho base do projeto, usado para definir caminhos relativos
BASE_DIR = Path(__file__).resolve().parents[2]


def parse_database_url(url: str, *, is_supabase: bool = False, enable_pool: bool = False) -> dict[str, Any]:
    """Interpreta DATABASE_URL / SUPABASE_DATABASE_URL com suporte a TLS e Supavisor/PgBouncer."""
    try:
        config = dj_database_url.parse(url, conn_max_age=0, conn_health_checks=True)
    except Exception as exc:
        raise ImproperlyConfigured('URL de banco de dados inválida.') from exc

    if config.get('ENGINE') == 'django.db.backends.sqlite3':
        if is_supabase:
            raise ImproperlyConfigured('SUPABASE_DATABASE_URL deve apontar para um banco PostgreSQL válido.')
        return config

    host = str(config.get('HOST') or '').lower().rstrip('.')
    supabase_detected = is_supabase or any(
        host == domain or host.endswith(f'.{domain}') for domain in ('supabase.co', 'supabase.com')
    )
    if supabase_detected and config.get('ENGINE') != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('A conexão com o Supabase deve utilizar PostgreSQL.')
    if supabase_detected and not all(config.get(key) for key in ('NAME', 'USER', 'PASSWORD', 'HOST')):
        raise ImproperlyConfigured('A URL do banco no Supabase deve conter nome, usuário, senha e host.')

    options = dict(config.get('OPTIONS') or {})
    is_external_pooler = host.endswith('.pooler.supabase.com') or str(config.get('PORT') or '') == '6543'
    if supabase_detected:
        options.setdefault('sslmode', 'require')
    if is_external_pooler:
        config['DISABLE_SERVER_SIDE_CURSORS'] = True
    elif enable_pool and config.get('ENGINE') == 'django.db.backends.postgresql':
        options.setdefault('pool', True)

    if options:
        config['OPTIONS'] = options
    else:
        config.pop('OPTIONS', None)
    return config


# Segurança e configuração básica
FRONTEND_URL = 'http://127.0.0.1:5173'
FRONTEND_ADMIN_URL = ''

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

# Aplicações instaladas
INSTALLED_APPS = [
    'daphne',
    'app.apps.NextRouterAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'cloudinary_storage',
    'cloudinary',
    'corsheaders',
    'django_extensions',
    'django_filters',
    'drf_spectacular',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'modules.uploads.apps.UploadsConfig',
    'modules.accounts.apps.AccountsConfig',
    'modules.organizations.apps.OrganizationsConfig',
    'modules.transport.apps.TransportConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'app.frontend.PrivateResponseMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'app.frontend.FrontendAssetsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'
ASGI_APPLICATION = 'app.asgi.application'

# Banco, cache e canais são escolhidos explicitamente em dev.py/prod.py.

# Validação de senhas
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Configurações de internacionalização
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Configurações de arquivos estáticos
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Coleta Django/admin é explícita e separada do build Vue em frontend_dist/.
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
FRONTEND_DIST = BASE_DIR / 'frontend_dist'

# Configurações de arquivos de mídia (App Uploader)
MEDIA_ENDPOINT = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
PRIVATE_DOCUMENT_ROOT = str(BASE_DIR / 'private-documents')
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880

# Configurações específicas para desenvolvimento, migração e produção
CLOUDINARY_URL = os.getenv('CLOUDINARY_URL')

# A configuração padrão de imagens usa Cloudinary quando configurado; documentos privados
# sempre usam PRIVATE_DOCUMENT_ROOT (modules/uploads/models/document.py).
MEDIA_STORAGE_BACKEND = (
    'cloudinary_storage.storage.MediaCloudinaryStorage'
    if CLOUDINARY_URL
    else 'django.core.files.storage.FileSystemStorage'
)

MEDIA_URL = '/media/'
STATICFILES_STORAGE_BACKEND = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Prefixo de imagens independente de MEDIA_URL; documentos privados não usam Cloudinary.
CLOUDINARY_STORAGE = {'PREFIX': 'media'}

STORAGES = {
    'default': {'BACKEND': MEDIA_STORAGE_BACKEND},
    'staticfiles': {'BACKEND': STATICFILES_STORAGE_BACKEND},
}

# Tipo padrão de campo para chaves primárias
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configurações do DRF e drf-spectacular (OpenAPI/Swagger)
SPECTACULAR_SETTINGS = {
    'TITLE': 'NEXTROUTER API',
    'DESCRIPTION': 'API para o projeto nextrouter.',
    'VERSION': '0.0.0',
    'ENUM_NAME_OVERRIDES': {
        'ServiceDirectionEnum': [('outbound', 'Ida'), ('return', 'Retorno')],
        'TravelStatusEnum': 'modules.transport.models.travel.Travel.Status',
        'VehicleStatusEnum': 'modules.transport.models.vehicle.Vehicle.Status',
        'LostItemStatusEnum': 'modules.transport.models.lost_item.LostItem.Status',
        'RouteOptimizationJobStatusEnum': 'modules.transport.models.route_optimization_job.RouteOptimizationJob.Status',
        'HabitualRouteKindEnum': 'modules.organizations.models.habitual_route.HabitualRoute.Kind',
    },
}

# Modelo de usuário personalizado
AUTH_USER_MODEL = 'authenticator.User'

# Configurações do Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('modules.accounts.authenticate.CustomAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_PAGINATION_CLASS': 'shared.pagination.CustomPagination',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'EXCEPTION_HANDLER': 'shared.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_RATES': {
        # Limita o envio/validação de códigos por e-mail, login, consulta de CEP e uploads públicos.
        'email_tokens': '60/hour',
        'login': '30/minute',
        'cep_lookup': '60/minute',
        'uploads': '120/hour',
    },
}

# Validade e número máximo de tentativas dos códigos de verificação enviados por e-mail
EMAIL_TOKEN_EXPIRATION_MINUTES = int(os.getenv('EMAIL_TOKEN_EXPIRATION_MINUTES', 15))
EMAIL_TOKEN_MAX_ATTEMPTS = int(os.getenv('EMAIL_TOKEN_MAX_ATTEMPTS', 5))
EMAIL_TOKEN_RESEND_SECONDS = int(os.getenv('EMAIL_TOKEN_RESEND_SECONDS', 60))
LOCATION_MAX_AGE_SECONDS = int(os.getenv('LOCATION_MAX_AGE_SECONDS', 30))
LOCATION_MIN_INTERVAL_SECONDS = int(os.getenv('LOCATION_MIN_INTERVAL_SECONDS', 2))
WS_REVALIDATION_SECONDS = 5
GEOCODING_URL = os.getenv('GEOCODING_URL', '')
GEOCODING_TIMEOUT_SECONDS = int(os.getenv('GEOCODING_TIMEOUT_SECONDS', 5))
GEOCODING_MAX_ATTEMPTS = int(os.getenv('GEOCODING_MAX_ATTEMPTS', 2))
OSRM_URL = os.getenv('OSRM_URL', '')
OSRM_TIMEOUT_SECONDS = int(os.getenv('OSRM_TIMEOUT_SECONDS', 8))
OSRM_MAX_ATTEMPTS = int(os.getenv('OSRM_MAX_ATTEMPTS', 2))
OSRM_MAX_STOPS = int(os.getenv('OSRM_MAX_STOPS', 20))
OSRM_MAX_SNAP_DISTANCE_METERS = int(os.getenv('OSRM_MAX_SNAP_DISTANCE_METERS', 100))
OSRM_CACHE_TIMEOUT_SECONDS = int(os.getenv('OSRM_CACHE_TIMEOUT_SECONDS', 3600))

# Limite de tamanho dos arquivos enviados ao App Uploader
MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024
MAX_DOCUMENT_UPLOAD_SIZE = 10 * 1024 * 1024

# Configurações do Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),  # Tokens de atualização expiram em 1 dia
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'CHECK_REVOKE_TOKEN': True,
    'UPDATE_LAST_LOGIN': True,
}

SECURE_CONTENT_TYPE_NOSNIFF = True


IPWARE_PROXY_COUNT = 1
IPWARE_HEADER_ORDER = ['X_FORWARDED_FOR', 'REMOTE_ADDR']


# Envio de email
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '').strip()
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL') or EMAIL_HOST_USER or 'webmaster@localhost'
# Sem timeout, um servidor SMTP lento deixa a requisição de cadastro travada indefinidamente.
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', 15))
