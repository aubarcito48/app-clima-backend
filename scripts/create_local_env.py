"""Crea un .env local con secreto aleatorio, sin mostrarlo ni sobrescribir archivos."""

from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parents[1]
    template = (root / ".env.example").read_text(encoding="utf-8")
    content = template.replace("DJANGO_SECRET_KEY=\n", f"DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\n", 1)
    try:
        with (root / ".env").open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(content)
    except FileExistsError:
        print("El .env ya existe; se conserva sin cambios.")
    else:
        print(".env local creado. El secreto permanece privado y no se muestra.")


if __name__ == "__main__":
    main()
