"""Suite reproducible sin leer .env, abrir red ni conectar una base de datos."""

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import sys
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shuffle", type=int, help="Semilla para variar el orden de las pruebas")
    parser.add_argument("--verbosity", type=int, choices=(0, 1, 2, 3), default=1)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.update({
        "PYTHON_DOTENV_DISABLED": "1",
        "DJANGO_SETTINGS_MODULE": "config.settings.development",
        "DJANGO_SECRET_KEY": "TEST-ONLY-NOT-A-REAL-SECRET-abcdefghijklmnopqrstuvwxyz-0123456789",
        "DJANGO_DEBUG": "false",
        "DJANGO_TRUST_PROXY_HTTPS": "false",
        "DJANGO_ALLOWED_HOSTS": "testserver,localhost,127.0.0.1",
        "CORS_ALLOWED_ORIGINS": "http://localhost:4200,http://127.0.0.1:4200",
        "OPENWEATHER_API_KEY": "",
        "OPENWEATHER_CONNECT_TIMEOUT_SECONDS": "3",
        "OPENWEATHER_READ_TIMEOUT_SECONDS": "5",
        "GROQ_API_KEY": "",
        "GROQ_MODEL": "",
        "GROQ_CONNECT_TIMEOUT_SECONDS": "3",
        "GROQ_READ_TIMEOUT_SECONDS": "8",
        "GROQ_MAX_COMPLETION_TOKENS": "160",
    })
    # Instalar los bloqueos antes de inicializar Django. Un acceso accidental
    # falla aun si el cliente de proveedor normalmente captura errores de red.
    with ExitStack() as stack:
        guards = [stack.enter_context(patch(target, side_effect=AssertionError(
            "La suite aislada no permite red ni conexiones a BD"
        ))) for target in (
            "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
            "sqlite3.connect", "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
        )]
        import django
        from django.core.management import call_command

        django.setup()
        options = {} if args.shuffle is None else {"shuffle": args.shuffle}
        call_command("test", "api", interactive=False, verbosity=args.verbosity, **options)
        for guard in guards:
            guard.assert_not_called()


if __name__ == "__main__":
    main()
