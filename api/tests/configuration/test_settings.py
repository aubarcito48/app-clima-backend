import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command, get_commands, load_command_class
from django.db import connections
from django.test import SimpleTestCase, override_settings

from config.settings.environment import env_bool, env_list, required_secret


class StatelessConfigurationTests(SimpleTestCase):
    def test_no_database_models_or_persistence_apps(self):
        forbidden_apps = {
            "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
            "django.contrib.sessions", "django.contrib.messages",
        }
        self.assertFalse(forbidden_apps.intersection(settings.INSTALLED_APPS))
        self.assertEqual(list(apps.get_models()), [])
        self.assertEqual(connections["default"].settings_dict["ENGINE"], "django.db.backends.dummy")
        self.assertFalse((settings.BASE_DIR / "db.sqlite3").exists())
        self.assertFalse((settings.BASE_DIR / "api" / "migrations").exists())
        self.assertFalse(any("sessions" in item or "auth" in item for item in settings.MIDDLEWARE))

    def test_system_checks_do_not_open_database_connections(self):
        with (
            patch("django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection", side_effect=AssertionError("No debe conectar una BD")),
            patch("sqlite3.connect", side_effect=AssertionError("No debe abrir SQLite")),
        ):
            call_command("check", verbosity=0)

    def test_local_runserver_does_not_invoke_the_migration_executor(self):
        self.assertEqual(get_commands()["runserver"], "api")
        command = load_command_class("api", "runserver")
        with patch("django.db.migrations.executor.MigrationExecutor") as executor:
            command.check_migrations()
        executor.assert_not_called()


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    CORS_ALLOWED_ORIGINS=["http://localhost:4200", "http://127.0.0.1:4200"],
    DEBUG=False,
)
class CorsConfigurationTests(SimpleTestCase):
    # La ruta no existe todavía: se prueba middleware, no un endpoint de TK03.
    path = "/api/v1/configuration-check/"

    def test_angular_origins_are_explicitly_allowed_without_a_database(self):
        for origin in settings.CORS_ALLOWED_ORIGINS:
            with self.subTest(origin=origin), patch(
                "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
                side_effect=AssertionError("No debe conectar una BD"),
            ):
                response = self.client.get(self.path, HTTP_ORIGIN=origin)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.headers["Access-Control-Allow-Origin"], origin)
                self.assertNotIn("Access-Control-Allow-Credentials", response.headers)

    def test_another_origin_does_not_receive_cors_authorization(self):
        response = self.client.get(self.path, HTTP_ORIGIN="https://not-allowed.example")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)

    def test_preflight_allows_get_for_the_authorized_origin(self):
        response = self.client.options(
            self.path,
            HTTP_ORIGIN="http://localhost:4200",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:4200")
        self.assertEqual(response.headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")

    def test_cors_does_not_apply_outside_the_api(self):
        response = self.client.get("/other/", HTTP_ORIGIN="http://localhost:4200")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_generic_error_does_not_expose_server_secrets(self):
        response = self.client.get(self.path)
        body = response.content.decode()
        for secret in [settings.SECRET_KEY, settings.OPENWEATHER_API_KEY, settings.GROQ_API_KEY]:
            if secret:
                self.assertTrue(secret not in body, "La respuesta no debe contener secretos")


class EnvironmentParsingTests(SimpleTestCase):
    def test_false_is_not_parsed_as_a_truthy_string(self):
        for value in ["false", "0", "no", "off", " FALSE "]:
            with self.subTest(value=value), patch.dict(os.environ, {"DJANGO_DEBUG": value}):
                self.assertFalse(env_bool("DJANGO_DEBUG"))

    def test_invalid_boolean_fails_instead_of_silently_enabling_debug(self):
        with patch.dict(os.environ, {"DJANGO_DEBUG": "maybe"}):
            with self.assertRaises(ImproperlyConfigured):
                env_bool("DJANGO_DEBUG")

    def test_lists_are_trimmed_and_empty_items_are_ignored(self):
        with patch.dict(os.environ, {"EXAMPLE_ORIGINS": " http://localhost:4200, , http://127.0.0.1:4200 "}):
            self.assertEqual(env_list("EXAMPLE_ORIGINS"), ["http://localhost:4200", "http://127.0.0.1:4200"])

    def test_empty_secret_is_rejected(self):
        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": " "}):
            with self.assertRaises(ImproperlyConfigured):
                required_secret()


class ProductionConfigurationTests(SimpleTestCase):
    def production_check(self, **overrides):
        environment = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": "TEST-ONLY-NOT-A-REAL-SECRET-abcdefghijklmnopqrstuvwxyz-0123456789",
            "DJANGO_DEBUG": "false",
            "DJANGO_ALLOWED_HOSTS": "api.example.invalid",
            "CORS_ALLOWED_ORIGINS": "https://frontend.example.invalid",
            "OPENWEATHER_API_KEY": "",
            "GROQ_API_KEY": "",
            **overrides,
        }
        return subprocess.run(
            [sys.executable, str(Path(settings.BASE_DIR) / "manage.py"), "check"],
            env=environment, capture_output=True, text=True, timeout=20,
        )

    def test_production_boots_without_provider_keys_or_database(self):
        result = self.production_check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_refuses_debug(self):
        result = self.production_check(DJANGO_DEBUG="true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_DEBUG debe ser false", result.stderr)

    def test_production_refuses_missing_or_wildcard_hosts(self):
        for hosts in ["", "*"]:
            with self.subTest(hosts=hosts):
                result = self.production_check(DJANGO_ALLOWED_HOSTS=hosts)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_production_refuses_empty_secret_without_printing_private_values(self):
        result = self.production_check(DJANGO_SECRET_KEY="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Falta DJANGO_SECRET_KEY", result.stderr)
        self.assertTrue(settings.SECRET_KEY not in result.stderr, "No debe imprimir el secreto local")
