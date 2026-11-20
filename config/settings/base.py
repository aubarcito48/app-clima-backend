"""Configuración común de la API sin almacenamiento persistente."""

import os
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

from .environment import env_bool, env_int, env_list, env_timeout, required_secret

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=False)

SECRET_KEY = required_secret()
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = ["corsheaders", "api.apps.ApiConfig"]
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "api.request_limits.ApiRequestLimitsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
TEMPLATES = []

# Django usa su backend dummy si no hay conexiones configuradas.
# No hay ORM de usuarios, sesiones ni migraciones. El catálogo geográfico SQLite
# se consulta aparte como archivo estático de solo lectura, sin conexión Django.
DATABASES = {}

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]
CORS_EXPOSE_HEADERS = ["Retry-After"]
CORS_URLS_REGEX = r"^/api(?:/|$)"

# Vacíos hasta integrar los proveedores. Nunca se entregan al frontend.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_CONNECT_TIMEOUT_SECONDS = env_timeout("OPENWEATHER_CONNECT_TIMEOUT_SECONDS", 3)
OPENWEATHER_READ_TIMEOUT_SECONDS = env_timeout("OPENWEATHER_READ_TIMEOUT_SECONDS", 5)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "").strip() or "openai/gpt-oss-20b"
GROQ_CONNECT_TIMEOUT_SECONDS = env_timeout("GROQ_CONNECT_TIMEOUT_SECONDS", 3)
GROQ_READ_TIMEOUT_SECONDS = env_timeout("GROQ_READ_TIMEOUT_SECONDS", 8)
GROQ_MAX_COMPLETION_TOKENS = env_int("GROQ_MAX_COMPLETION_TOKENS", 160, minimum=32, maximum=512)
GROQ_GUARD_ENABLED = env_bool('GROQ_GUARD_ENABLED', default=True)
GROQ_CACHE_TTL_SECONDS = env_int('GROQ_CACHE_TTL_SECONDS', 300, minimum=1, maximum=900)
GROQ_CACHE_MAX_ENTRIES = env_int('GROQ_CACHE_MAX_ENTRIES', 512, minimum=1, maximum=5000)
# Set hops only after verifying that the ingress appends/overwrites X-Forwarded-For.
API_TRUSTED_PROXY_HOPS = env_int('API_TRUSTED_PROXY_HOPS', 0, minimum=0, maximum=5)
API_VISITOR_REQUESTS_PER_MINUTE = {
    '/api/v1/mapa/': 24,
    '/api/v1/clima/': 6, '/api/v1/lugares/': 40,
    '/api/v1/alertas/': 20, '/api/v1/voz/': 3,
}
API_VISITOR_MAX_ENTRIES = 4096
ISA_DIRECTOR = os.getenv('ISA_DIRECTOR', 'groq').strip().lower()
if ISA_DIRECTOR not in ('groq', 'local'):
    raise ImproperlyConfigured('ISA_DIRECTOR must be groq or local')
ISA_MODEL_DIR = Path(os.getenv('ISA_MODEL_DIR', '').strip() or BASE_DIR / 'models' / 'piper-sharvard')
ISA_VOICE_KEEPALIVE_SECONDS = env_int('ISA_VOICE_KEEPALIVE_SECONDS', 0, minimum=0, maximum=120)
ISA_VOICE_STREAM_ENABLED = env_bool('ISA_VOICE_STREAM_ENABLED', default=True)
ISA_LIP_SYNC = os.getenv('ISA_LIP_SYNC', 'own').strip().lower()
# Legacy deployment value selects our engine too; no Rhubarb process is launched.
if ISA_LIP_SYNC not in ('off', 'own', 'rhubarb'):
    raise ImproperlyConfigured('ISA_LIP_SYNC must be own or off')

# Límites compartidos por todos los visitantes del proceso, sin confiar en X-Forwarded-For.
API_RATE_LIMIT_ENABLED = False
SMN_BACKGROUND_RECOVERY = False
API_REQUESTS_PER_MINUTE = {
    '/api/v1/mapa/': env_int('API_MAP_REQUESTS_PER_MINUTE', 40, minimum=1, maximum=60),
    '/api/v1/clima/': env_int('API_CLIMATE_REQUESTS_PER_MINUTE', 30, minimum=1, maximum=300),
    '/api/v1/lugares/': env_int('API_PLACES_REQUESTS_PER_MINUTE', 120, minimum=1, maximum=600),
    '/api/v1/alertas/': env_int('API_ALERTS_REQUESTS_PER_MINUTE', 60, minimum=1, maximum=300),
    '/api/v1/voz/': env_int('API_VOICE_REQUESTS_PER_MINUTE', 6, minimum=1, maximum=60),
}

# Evitar que el logging verbose del SDK/transporte propague prompts o cabeceras.
# Los logs operativos de Django se mantienen; no se registran cuerpos de Groq.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"provider_silent": {"class": "logging.NullHandler"}},
    "loggers": {
        name: {"handlers": ["provider_silent"], "level": "WARNING", "propagate": False}
        for name in ("groq", "httpx", "httpcore")
    },
}
