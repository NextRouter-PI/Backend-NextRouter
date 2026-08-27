import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Define o modo de execução da aplicação
MODE = os.getenv('MODE')

# Constrói o caminho base do projeto, usado para definir caminhos relativos
BASE_DIR = Path(__file__).resolve().parent.parent

# Segurança e configuração básica
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
# No Fabroku, defina ALLOWED_HOSTS (ex.: "seu-app.fabroku.app") como variável de ambiente;
# o fallback abaixo só cobre desenvolvimento local.
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')
FRONTEND_ADMIN_URL = os.getenv('FRONTEND_ADMIN_URL', '')

_default_origins = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:3000',
    'http://localhost:8000',
    'https://next-router-frontend.vercel.app',
    'https://next-router-admin.vercel.app',
]
_extra_origins = [origin.strip() for origin in (FRONTEND_URL, FRONTEND_ADMIN_URL) if origin.strip()]

CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_default_origins + _extra_origins))
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = list(dict.fromkeys(_default_origins + _extra_origins))

CORS_ALLOW_CREDENTIALS = True

# Aplicações instaladas
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 'django.contrib.gis',
    'channels',
    'cloudinary_storage',
    'cloudinary',
    'corsheaders',
    'django_extensions',
    'django_filters',
    'drf_spectacular',
    'rest_framework',
    'authenticator',
    'uploader',
    'router',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

REDIS_URL = os.getenv('REDIS_URL')

if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        },
    }
else:
    # Sem Redis configurado (ex.: desenvolvimento local): usa a camada em memória.
    # Funciona apenas dentro de um único processo — não use em produção com múltiplos workers.
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Banco de dados
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

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
STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Configurações de arquivos de mídia (App Uploader)
MEDIA_ENDPOINT = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880

# Configurações específicas para desenvolvimento, migração e produção
CLOUDINARY_URL = os.getenv('CLOUDINARY_URL')

# Sempre que houver credenciais do Cloudinary configuradas (dev ou produção), os arquivos
# enviados (imagens e documentos) são salvos no Cloudinary; os metadados (attachment_key,
# public_id, descrição etc.) continuam sendo salvos normalmente no banco de dados.
MEDIA_STORAGE_BACKEND = (
    'cloudinary_storage.storage.MediaCloudinaryStorage'
    if CLOUDINARY_URL
    else 'django.core.files.storage.FileSystemStorage'
)

if MODE == 'DEVELOPMENT':
    MY_IP = os.getenv('MY_IP', '127.0.0.1')
    BACKEND_HOST = os.getenv('BACKEND_HOST', '127.0.0.1')
    BACKEND_PORT = os.getenv('BACKEND_PORT', '8000')
    STATICFILES_STORAGE_BACKEND = 'django.contrib.staticfiles.storage.StaticFilesStorage'
    # Só é usada como fallback quando não há Cloudinary configurado (arquivos servidos localmente).
    MEDIA_URL = f'http://{BACKEND_HOST}:{BACKEND_PORT}/media/'
else:
    MEDIA_URL = '/media/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    STATICFILES_STORAGE_BACKEND = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# django-cloudinary-storage usa `MEDIA_URL` como prefixo de pasta por padrão quando
# `CLOUDINARY_STORAGE['PREFIX']` não é definido. Como aqui `MEDIA_URL` é uma URL absoluta
# (ex.: "http://127.0.0.1:8000/media/"), isso corrompia o nome/pasta de todo arquivo salvo
# no Cloudinary. Fixamos um prefixo relativo próprio, independente de `MEDIA_URL`.
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
}

# Modelo de usuário personalizado
AUTH_USER_MODEL = 'authenticator.User'

# Configurações do Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PAGINATION_CLASS': 'app.pagination.CustomPagination',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',)
}

# Configurações do Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=180),  # Tokens de acesso expiram em 3 horas
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),  # Tokens de atualização expiram em 1 dia
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Exibe as configurações principais para verificação
print(f'{MODE = } \n{MEDIA_URL = } \n{DATABASES = }')


# Envio de email
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'webmaster@localhost')

if not EMAIL_HOST:
    # Sem SMTP configurado (ex.: ambiente de desenvolvimento): imprime os e-mails no console
    # em vez de falhar ao tentar enviar de verdade.
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
