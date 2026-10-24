"""Base de producción. El despliegue y su revisión completa quedan para TK09–TK10."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .environment import env_bool

if env_bool("DJANGO_DEBUG", default=False):
    raise ImproperlyConfigured("DJANGO_DEBUG debe ser false en producción.")

DEBUG = False

if not ALLOWED_HOSTS or any("*" in host for host in ALLOWED_HOSTS):  # noqa: F405
    raise ImproperlyConfigured("Producción requiere DJANGO_ALLOWED_HOSTS explícitos, sin comodines.")

if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY de producción debe ser privada y robusta.")
