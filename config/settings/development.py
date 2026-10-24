"""Entorno local para Angular en localhost o 127.0.0.1:4200."""

from .base import *  # noqa: F403
from .environment import env_bool, env_list

DEBUG = env_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ("localhost", "127.0.0.1", "[::1]"))
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", ("http://localhost:4200", "http://127.0.0.1:4200")
)
