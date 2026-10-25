"""Configuración común de la API sin persistencia."""

import os
from pathlib import Path

from dotenv import load_dotenv

from .environment import env_int, env_list, env_timeout, required_secret

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=False)

SECRET_KEY = required_secret()
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = ["corsheaders", "api.apps.ApiConfig"]
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
TEMPLATES = []

# Django usa su backend dummy si no hay conexiones configuradas.
# No hay SQLite, ORM de la aplicación, sesiones ni migraciones que ejecutar.
DATABASES = {}

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_METHODS = ["GET", "OPTIONS"]
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
