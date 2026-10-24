"""Lectura explícita de configuración; nunca registra valores secretos."""

import os
import math
import ipaddress
import re
from urllib.parse import urlsplit

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


def exact_host(value):
    """Host concreto, sin esquema, puerto, comodín ni sufijo de dominio."""
    try:
        ipaddress.ip_address(value[1:-1] if value.startswith("[") and value.endswith("]") else value)
        return ":" not in value or value.startswith("[")
    except ValueError:
        return bool(len(value) <= 253 and all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in value.split(".")
        ))


def explicit_origin(value):
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
        return bool(
            host and exact_host(f"[{host}]" if ":" in host else host)
            and parsed.username is None and parsed.password is None
            and not parsed.netloc.endswith(":")
            and not parsed.path and not parsed.query and not parsed.fragment
            and (port is None or 0 < port <= 65535)
            and (parsed.scheme == "https" or (
                parsed.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}
            ))
            and value == f"{parsed.scheme}://{parsed.netloc}"
        )
    except ValueError:
        return False
