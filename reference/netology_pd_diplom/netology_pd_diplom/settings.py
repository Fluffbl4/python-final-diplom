"""
Django settings for netology_pd_diplom project.
"""

import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from datetime import timedelta

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '=hs6$#5om031nujz4staql9mbuste=!dc^6)4opsjq!vvjxzj@'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'baton',  # django-baton для улучшения админки
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'django_rest_passwordreset',
    'drf_spectacular',  # OpenAPI документация
    'social_django',  # OAuth авторизация
    'imagekit',  # Обработка изображений
    'cachalot',  # Кэширование запросов
    'silk',  # Профилирование

    # Local apps
    'backend',

    # baton должен быть последним
    'baton.autodiscover',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Social auth middleware
    'social_django.middleware.SocialAuthExceptionMiddleware',

    # Silk middleware для профилирования
    'silk.middleware.SilkyMiddleware',
]

ROOT_URLCONF = 'netology_pd_diplom.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # Social auth context processors
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'netology_pd_diplom.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Password validation
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

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Media files (для аватаров и изображений товаров)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

AUTH_USER_MODEL = 'backend.User'

# Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.mail.ru'
EMAIL_HOST_USER = 'netology.diplom@mail.ru'
EMAIL_HOST_PASSWORD = 'CLdm7yW4U9nivz9mbexu'
EMAIL_PORT = '465'
EMAIL_USE_SSL = True
SERVER_EMAIL = EMAIL_HOST_USER
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

ADMIN_EMAILS = ['netology.diplom@mail.ru']
BASE_URL = 'http://localhost:8000'

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 40,

    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),

    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Для OAuth
    ),

    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',  # OpenAPI

    # Throttling settings
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    }
}

# DRF Spectacular settings (OpenAPI)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Shop API',
    'DESCRIPTION': 'API для интернет-магазина с поддержкой покупателей и партнеров',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
    }
}

# Social Auth settings (OAuth)
AUTHENTICATION_BACKENDS = (
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.vk.VKOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)

# Google OAuth2 settings (замените на реальные ключи)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = 'your-google-client-id.apps.googleusercontent.com'
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = 'your-google-client-secret'

# VK OAuth2 settings (замените на реальные ключи)
SOCIAL_AUTH_VK_OAUTH2_KEY = 'your-vk-app-id'
SOCIAL_AUTH_VK_OAUTH2_SECRET = 'your-vk-secret-key'
SOCIAL_AUTH_VK_OAUTH2_SCOPE = ['email']

SOCIAL_AUTH_URL_NAMESPACE = 'social'
SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'
SOCIAL_AUTH_LOGIN_ERROR_URL = '/login-error/'

# Pipeline для социальной авторизации
SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
)

# Baton admin configuration
BATON = {
    'SITE_HEADER': 'Shop Administration',
    'SITE_TITLE': 'Shop Admin',
    'INDEX_TITLE': 'Site administration',
    'SUPPORT_HREF': 'https://github.com/otto-torino/django-baton/issues',
    'COPYRIGHT': 'copyright © 2024 Shop Admin',
    'POWERED_BY': '<a href="https://www.djangoproject.com/">Django</a>',
    'CONFIRM_UNSAVED_CHANGES': True,
    'SHOW_MULTIPART_UPLOADING': True,
    'ENABLE_IMAGES_PREVIEW': True,
    'CHANGELIST_FILTERS_IN_MODAL': True,
    'MENU_ALWAYS_COLLAPSED': False,
    'MENU_TITLE': 'Menu',
    'GRAVATAR_DEFAULT_IMG': 'retro',
    'LOGIN_SPLASH': '/static/core/img/login-splash.png',
}

# Cache settings (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'shop'
    }
}

# Cachalot settings (кэширование запросов)
CACHALOT_ENABLED = True
CACHALOT_UNCACHABLE_TABLES = ('django_migrations', 'silk_')

# Silk settings (профилирование)
SILKY_PYTHON_PROFILER = True
SILKY_PYTHON_PROFILER_BINARY = True
SILKY_META = True
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_MAX_RECORDED_REQUESTS = 10**4
SILKY_INTERCEPT_PERCENT = 50  # Процент запросов для профилирования

# Настройки для сброса пароля
DJANGO_REST_PASSWORDRESET_TOKEN_CONFIG = {
    "CLASS": "django_rest_passwordreset.tokens.RandomStringTokenGenerator",
    "OPTIONS": {
        "min_length": 20,
        "max_length": 30
    }
}

# Настройки для подтверждения email
CONFIRM_EMAIL_TOKEN_LIFETIME = 24  # часов

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


sentry_sdk.init(
    dsn="https://your-sentry-dsn@o4500000000.ingest.sentry.io/0000000",
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True,
    environment="development" if DEBUG else "production",
)