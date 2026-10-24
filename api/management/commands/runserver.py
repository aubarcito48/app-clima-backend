from django.core.management.commands.runserver import Command as DjangoRunserver


class Command(DjangoRunserver):
    def check_migrations(self):
        """Esta API no tiene BD ni migraciones; mantiene los demás system checks."""
