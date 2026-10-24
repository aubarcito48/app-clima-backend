"""Lectura explícita de configuración; nunca registra valores secretos."""

import os
import math

from django.core.exceptions import ImproperlyConfigured


def env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"true", "1", "yes", "on"}:
        return True
    if value in {"false", "0", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} debe ser un booleano explícito: true o false.")


def env_list(name, default=()):
    raw = os.getenv(name)
    if raw is None:
        return list(default)
    return [value.strip() for value in raw.split(",") if value.strip()]


def required_secret():
    value = os.getenv("DJANGO_SECRET_KEY", "").strip()
    if not value:
        raise ImproperlyConfigured(
            "Falta DJANGO_SECRET_KEY. Prepará el .env local o las variables del servidor."
        )
    return value


def env_timeout(name, default):
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        raise ImproperlyConfigured(f"{name} debe ser un número de segundos entre 0 y 30.") from None
    if not math.isfinite(value) or not 0 < value <= 30:
        raise ImproperlyConfigured(f"{name} debe ser mayor que 0 y no superar 30 segundos.")
    return value


def env_int(name, default, *, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ImproperlyConfigured(f"{name} debe ser un entero entre {minimum} y {maximum}.") from None
    if not minimum <= value <= maximum:
        raise ImproperlyConfigured(f"{name} debe estar entre {minimum} y {maximum}.")
    return value
