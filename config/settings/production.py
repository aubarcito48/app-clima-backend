"""Producción sin persistencia. El despliegue pertenece a TK10."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .environment import env_bool, exact_host, explicit_origin

if env_bool("DJANGO_DEBUG", default=False):
    raise ImproperlyConfigured("DJANGO_DEBUG debe ser false en producción.")

DEBUG = False

if not ALLOWED_HOSTS or not all(exact_host(host) for host in ALLOWED_HOSTS):  # noqa: F405
    raise ImproperlyConfigured("Producción requiere DJANGO_ALLOWED_HOSTS explícitos, sin comodines.")

if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY de producción debe ser privada y robusta.")

if not CORS_ALLOWED_ORIGINS or not all(explicit_origin(origin) for origin in CORS_ALLOWED_ORIGINS):  # noqa: F405
    raise ImproperlyConfigured("Producción requiere CORS_ALLOWED_ORIGINS explícitos con HTTPS; HTTP solo para loopback local.")

SECURE_SSL_REDIRECT = True
# Activar solo cuando el proxy elimine el encabezado enviado por el cliente y
# establezca su propio valor. Verificar esa condición en el hosting de TK10.
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https") if env_bool("DJANGO_TRUST_PROXY_HTTPS") else None
)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# HSTS acotado al host, sin compromiso de subdominios/preload antes del despliegue.
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

MIDDLEWARE = ["api.operational.OperationalMiddleware", *MIDDLEWARE]  # noqa: F405
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"safe": {"()": "api.operational.SafeOperationalFormatter"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "safe", "stream": "ext://sys.stdout"},
        "silent": {"class": "logging.NullHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        **{name: {"handlers": ["console"], "level": "INFO", "propagate": False}
           for name in ("django", "django.request", "django.server", "django.security", "api.operations")},
        **{name: {"handlers": ["silent"], "level": "WARNING", "propagate": False}
           for name in ("groq", "httpx", "httpcore")},
    },
}
