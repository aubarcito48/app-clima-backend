"""CP12/CP13: configuración y recorrido HTTP real con ajustes de producción."""

import json
import logging
import os
from pathlib import Path
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

from config.settings.environment import exact_host, explicit_origin
from .operational import SafeOperationalFormatter


class ProductionSecurityTests(SimpleTestCase):
    def run_production(self, code="from django.core.management import call_command; call_command('check')", **overrides):
        environment = {
            **os.environ, "PYTHON_DOTENV_DISABLED": "1",
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": "TEST-ONLY-abcdefghijklmnopqrstuvwxyz-0123456789-ROBUST-SECRET",
            "DJANGO_DEBUG": "false", "DJANGO_ALLOWED_HOSTS": "api.example.invalid",
            "CORS_ALLOWED_ORIGINS": "https://frontend.example.invalid,http://localhost:4200",
            "DJANGO_TRUST_PROXY_HTTPS": "false",
            "OPENWEATHER_API_KEY": "PRIVATE-WEATHER-KEY", "GROQ_API_KEY": "PRIVATE-GROQ-KEY",
            **overrides,
        }
        return subprocess.run(
            [sys.executable, "-c", "import django; django.setup(); " + code],
            cwd=Path(settings.BASE_DIR), env=environment,
            capture_output=True, text=True, timeout=20,
        )

    def test_hosts_are_exact_and_origins_have_no_credentials_paths_or_wildcards(self):
        for host in ("api.example.invalid", "localhost", "127.0.0.1", "[::1]"):
            self.assertTrue(exact_host(host), host)
        for host in ("*", ".example.invalid", "https://api.example.invalid", "api.example.invalid:443", "a/b", "", "bad_name"):
            self.assertFalse(exact_host(host), host)
        for origin in ("https://frontend.example.invalid", "http://localhost:4200", "http://127.0.0.1:4200", "http://[::1]:4200"):
            self.assertTrue(explicit_origin(origin), origin)
        for origin in ("*", "https://*.example.invalid", "http://frontend.example.invalid", "https://x/", "https://u:p@x", "https://@x", "https://x:", "https://x:0", "https://x:99999", "https://x?key=value", "https://x#f", "null"):
            self.assertFalse(explicit_origin(origin), origin)

    def test_invalid_production_values_fail_without_echoing_the_value(self):
        for overrides, expected in (
            ({"DJANGO_ALLOWED_HOSTS": ".PRIVATE-HOST.invalid"}, "DJANGO_ALLOWED_HOSTS"),
            ({"CORS_ALLOWED_ORIGINS": ""}, "CORS_ALLOWED_ORIGINS"),
            ({"CORS_ALLOWED_ORIGINS": "https://PRIVATE-USER:PRIVATE-PASS@x.invalid"}, "CORS_ALLOWED_ORIGINS"),
            ({"DJANGO_SECRET_KEY": "a" * 60}, "DJANGO_SECRET_KEY"),
            ({"DJANGO_TRUST_PROXY_HTTPS": "PRIVATE-INVALID"}, "DJANGO_TRUST_PROXY_HTTPS"),
        ):
            with self.subTest(field=expected):
                result = self.run_production(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                for secret in ("PRIVATE-USER", "PRIVATE-PASS", "PRIVATE-HOST", "PRIVATE-INVALID", "a" * 60):
                    self.assertNotIn(secret, result.stdout + result.stderr)

    def test_safe_formatter_drops_messages_arguments_requests_and_tracebacks(self):
        record = logging.LogRecord("django.request", logging.ERROR, "PRIVATE-FILE", 1,
            "https://provider.invalid/?appid=%s", ("PRIVATE-KEY",), (ValueError, ValueError("PRIVATE-PROMPT"), None))
        record.request = "PRIVATE-REQUEST"
        record.api_route = "PRIVATE-ROUTE"
        record.status_code = 503
        formatted = SafeOperationalFormatter().format(record)
        self.assertEqual(json.loads(formatted)["status"], 503)
        self.assertNotIn("PRIVATE", formatted)
        self.assertNotIn("appid", formatted)
        self.assertNotIn("Traceback", formatted)

    def test_production_http_cors_errors_headers_and_console_logs_do_not_expose_secrets(self):
        code = '''
from unittest.mock import patch
from django.test import Client
client = Client(raise_request_exception=False, HTTP_HOST='api.example.invalid')
with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection', side_effect=AssertionError('DB forbidden')):
    for origin in ('https://frontend.example.invalid', 'http://localhost:4200', 'https://other.invalid'):
        response = client.get('/api/v1/health/?appid=PRIVATE-QUERY', secure=True, HTTP_ORIGIN=origin)
        assert response.status_code == 200
        assert response.has_header('Access-Control-Allow-Origin') == (origin != 'https://other.invalid')
        if origin != 'https://other.invalid':
            assert response['Access-Control-Allow-Origin'] == origin
        assert not response.has_header('Access-Control-Allow-Credentials')
        assert response['Strict-Transport-Security'] == 'max-age=3600'
        assert response['X-Content-Type-Options'] == 'nosniff'
        assert response['X-Frame-Options'] == 'DENY'
        assert response['Referrer-Policy'] == 'no-referrer'
        assert response['Cache-Control'] == 'no-store'
    assert client.get('/api/v1/health/').status_code == 301
    assert client.get('/api/v1/health/', secure=True, HTTP_HOST='wrong.invalid').status_code == 400
    response = client.options('/api/v1/clima/', secure=True, HTTP_ORIGIN='https://frontend.example.invalid', HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET')
    assert response.status_code == 200
    assert response['Access-Control-Allow-Methods'] == 'GET, POST, OPTIONS'
    with patch('api.views.query_climate', side_effect=RuntimeError('PRIVATE-EXCEPTION appid=PRIVATE-WEATHER-KEY PRIVATE-PROMPT')):
        response = client.get('/api/v1/clima/?ciudad=PRIVATE-CITY', secure=True, HTTP_ORIGIN='https://frontend.example.invalid')
        assert response.status_code == 500
        assert response.json() == {'codigo': 'SERVICIO_NO_DISPONIBLE', 'mensaje': 'No se pudo completar la consulta. Intentá más tarde.'}
        assert response['Access-Control-Allow-Origin'] == 'https://frontend.example.invalid'
        assert response['Cache-Control'] == 'no-store'
        assert b'PRIVATE' not in response.content
'''
        result = self.run_production(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"event": "http_response"', result.stdout)
        self.assertIn('"status": 500', result.stdout)
        for private in ("PRIVATE", "appid", "Traceback", "RuntimeError"):
            self.assertNotIn(private, result.stdout + result.stderr)

    def test_forwarded_https_is_trusted_only_when_explicitly_enabled(self):
        code = "from django.test import Client; from django.conf import settings; r=Client(HTTP_HOST='api.example.invalid').get('/api/v1/health/',HTTP_X_FORWARDED_PROTO='https'); assert r.status_code == (200 if settings.SECURE_PROXY_SSL_HEADER else 301)"
        for enabled in ("true", "false"):
            with self.subTest(enabled=enabled):
                result = self.run_production(code, DJANGO_TRUST_PROXY_HTTPS=enabled)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_deployment_checks_report_only_documented_policy_choices(self):
        code = "from django.core.checks import run_checks; issues=run_checks(include_deployment_checks=True); assert {i.id for i in issues} == {'security.W003','security.W005','security.W021'}, [i.id for i in issues]"
        result = self.run_production(code)
        self.assertEqual(result.returncode, 0, result.stderr)
