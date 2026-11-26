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
        'DIRS': [BASE_DIR / 'templates'],
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
# Quanto antes da saída prevista o motorista já pode iniciar a viagem.
TRAVEL_START_EARLY_MINUTES = int(os.getenv('TRAVEL_START_EARLY_MINUTES', 60))
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


def _parse_optional_bool(env, name: str) -> bool | None:
    raw = env.get(name)
    if raw is None or not str(raw).strip():
        return None
    normalized = str(raw).strip().lower()
    if normalized in {'true', '1', 'yes', 'on'}:
        return True
    if normalized in {'false', '0', 'no', 'off'}:
        return False
    raise ImproperlyConfigured(f'{name} deve ser um booleano válido (true/false).')


def resolve_email_settings(
    env=None, *, strict: bool = False, fallback_from: str = 'webmaster@localhost'
) -> dict[str, Any]:
    """Seleciona automaticamente o backend de e-mail conforme as variáveis de ambiente.

    Prioridade:
    1. EMAIL_BACKEND explícito no ambiente (se informado);
    2. BREVO_API_KEY preenchida -> API HTTP v3 do Brevo;
    3. EMAIL_HOST preenchido (ou conta Gmail com usuário/senha) -> SMTP (Gmail, Brevo SMTP, etc.);
    4. Fallback seguro para console.
    """
    source = os.environ if env is None else env
    explicit_backend = str(source.get('EMAIL_BACKEND') or '').strip()
    brevo_api_key = str(source.get('BREVO_API_KEY') or '').strip()
    email_host = str(source.get('EMAIL_HOST') or '').strip()
    email_host_user = str(source.get('EMAIL_HOST_USER') or '').strip()
    email_host_password = str(source.get('EMAIL_HOST_PASSWORD') or '').strip()
    explicit_from = str(source.get('DEFAULT_FROM_EMAIL') or source.get('BREVO_SENDER_EMAIL') or '').strip()

    use_tls = _parse_optional_bool(source, 'EMAIL_USE_TLS')
    use_ssl = _parse_optional_bool(source, 'EMAIL_USE_SSL')
    if use_tls is True and use_ssl is True:
        raise ImproperlyConfigured('EMAIL_USE_TLS e EMAIL_USE_SSL não podem ser ativados simultaneamente.')

    raw_port = str(source.get('EMAIL_PORT') or '').strip()
    if raw_port:
        try:
            email_port = int(raw_port)
        except ValueError as exc:
            raise ImproperlyConfigured('EMAIL_PORT deve ser um número inteiro válido.') from exc
    else:
        email_port = 465 if use_ssl is True else 587

    if not email_host and not brevo_api_key and email_host_user.lower().endswith('@gmail.com') and email_host_password:
        email_host = 'smtp.gmail.com'

    if explicit_backend:
        backend = explicit_backend
    elif brevo_api_key:
        backend = 'app.email_backends.BrevoEmailBackend'
    elif email_host:
        backend = 'django.core.mail.backends.smtp.EmailBackend'
    else:
        backend = 'django.core.mail.backends.console.EmailBackend'

    if backend == 'app.email_backends.BrevoEmailBackend':
        if strict and not brevo_api_key:
            raise ImproperlyConfigured('BREVO_API_KEY é obrigatório para o backend Brevo.')
        default_from = explicit_from or email_host_user
        if strict and not default_from:
            raise ImproperlyConfigured('DEFAULT_FROM_EMAIL é obrigatório em produção com Brevo.')
        default_from = default_from or fallback_from
        resolved_tls = bool(use_tls)
        resolved_ssl = bool(use_ssl)
    elif backend == 'django.core.mail.backends.smtp.EmailBackend':
        if strict and not email_host:
            raise ImproperlyConfigured('EMAIL_HOST é obrigatório para envio via SMTP.')
        if strict and not email_host_user:
            raise ImproperlyConfigured('EMAIL_HOST_USER é obrigatório em produção com SMTP.')
        if strict and not email_host_password:
            raise ImproperlyConfigured('EMAIL_HOST_PASSWORD é obrigatório em produção com SMTP.')
        if use_tls is None and use_ssl is None:
            resolved_ssl = email_port == 465
            resolved_tls = email_port == 587
        else:
            resolved_tls = bool(use_tls)
            resolved_ssl = bool(use_ssl)
        default_from = explicit_from or email_host_user or fallback_from
    else:
        resolved_tls = bool(use_tls)
        resolved_ssl = bool(use_ssl)
        default_from = explicit_from or email_host_user or fallback_from

    raw_timeout = str(source.get('EMAIL_TIMEOUT') or '15').strip()
    try:
        email_timeout = int(raw_timeout)
    except ValueError as exc:
        raise ImproperlyConfigured('EMAIL_TIMEOUT deve ser um número inteiro válido.') from exc

    return {
        'EMAIL_BACKEND': backend,
        'BREVO_API_KEY': brevo_api_key,
        'EMAIL_HOST': email_host,
        'EMAIL_HOST_USER': email_host_user,
        'EMAIL_HOST_PASSWORD': email_host_password,
        'EMAIL_USE_TLS': resolved_tls,
        'EMAIL_USE_SSL': resolved_ssl,
        'EMAIL_PORT': email_port,
        'DEFAULT_FROM_EMAIL': default_from,
        'EMAIL_TIMEOUT': email_timeout,
    }


# Envio de email
_email_settings = resolve_email_settings(os.environ, strict=False, fallback_from='webmaster@localhost')
EMAIL_BACKEND = _email_settings['EMAIL_BACKEND']
BREVO_API_KEY = _email_settings['BREVO_API_KEY']
EMAIL_HOST = _email_settings['EMAIL_HOST']
EMAIL_HOST_USER = _email_settings['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = _email_settings['EMAIL_HOST_PASSWORD']
EMAIL_USE_TLS = _email_settings['EMAIL_USE_TLS']
EMAIL_USE_SSL = _email_settings['EMAIL_USE_SSL']
EMAIL_PORT = _email_settings['EMAIL_PORT']
DEFAULT_FROM_EMAIL = _email_settings['DEFAULT_FROM_EMAIL']
# Sem timeout, um servidor SMTP lento deixa a requisição de cadastro travada indefinidamente.
EMAIL_TIMEOUT = _email_settings['EMAIL_TIMEOUT']
