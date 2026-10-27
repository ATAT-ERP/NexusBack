"""Tests for technical project-level behavior."""

import json
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase


class HealthCheckTests(SimpleTestCase):
    def test_health_check_reports_process_availability(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})


class SettingsEnvironmentTests(SimpleTestCase):
    def load_settings(self, **overrides):
        """Importa settings sin depender de .env ni del ejecutor de pruebas.

        @version 1.0
        @author Agustin
        """
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("DJANGO_", "CORS_", "CSRF_", "POSTGRES_"))
        }
        environment.update(
            NEXUS_SKIP_DOTENV="1",
            DJANGO_SETTINGS_MODULE="config.settings",
            DJANGO_DEBUG="True",
            DJANGO_SECRET_KEY="configuration-tests-only",
            POSTGRES_DB="configuration-tests-only",
            POSTGRES_USER="configuration-tests-only",
            DB_PASSWORD="configuration-tests-only",
            POSTGRES_HOST="test-db",
            POSTGRES_PORT="5432",
            SUPABASE_URL="https://example.invalid",
            SUPABASE_KEY="configuration-tests-only",
            SUPABASE_SECRET_KEY="configuration-tests-only",
        )
        environment.update(overrides)
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "import django; django.setup(); import json; "
                "from django.conf import settings; "
                "print(json.dumps({name: getattr(settings, name) for name in "
                "['DEBUG', 'ALLOWED_HOSTS', 'CORS_ALLOWED_ORIGINS', "
                "'CSRF_TRUSTED_ORIGINS', 'SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE', "
                "'CSRF_COOKIE_SECURE', 'SECURE_HSTS_SECONDS', "
                "'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'SECURE_HSTS_PRELOAD', "
                "'SECURE_PROXY_SSL_HEADER', "
                "'DATABASES']}))",
            ],
            cwd=Path(__file__).resolve().parent.parent,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_local_defaults_allow_loopback_and_android_without_https(self):
        """Permite clientes locales sin una IP personal.

        @version 1.0
        @author Agustin
        """
        result = self.load_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        configuration = json.loads(result.stdout)
        self.assertEqual(configuration["ALLOWED_HOSTS"], ["localhost", "127.0.0.1", "10.0.2.2"])
        self.assertEqual(configuration["CORS_ALLOWED_ORIGINS"], [
            "http://localhost:5173", "http://127.0.0.1:5173",
        ])
        self.assertFalse(configuration["SECURE_SSL_REDIRECT"])
        self.assertFalse(configuration["CSRF_COOKIE_SECURE"])
        self.assertFalse(configuration["SESSION_COOKIE_SECURE"])
        self.assertEqual(configuration["SECURE_HSTS_SECONDS"], 0)
        self.assertFalse(configuration["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
        self.assertFalse(configuration["SECURE_HSTS_PRELOAD"])
        self.assertIsNone(configuration["SECURE_PROXY_SSL_HEADER"])

    def test_explicit_lists_replace_defaults(self):
        """Respeta los hosts y orígenes configurados explícitamente.

        @version 1.0
        @author Agustin
        """
        result = self.load_settings(
            DJANGO_ALLOWED_HOSTS=" localhost, 127.0.0.1, ",
            CORS_ALLOWED_ORIGINS="http://localhost:3000, ",
            CSRF_TRUSTED_ORIGINS=" http://localhost:3000, ",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        configuration = json.loads(result.stdout)
        self.assertEqual(configuration["ALLOWED_HOSTS"], ["localhost", "127.0.0.1"])
        self.assertEqual(configuration["CORS_ALLOWED_ORIGINS"], ["http://localhost:3000"])
        self.assertEqual(configuration["CSRF_TRUSTED_ORIGINS"], ["http://localhost:3000"])

    def test_production_requires_secure_key_explicit_hosts_and_https_origins(self):
        """Rechaza valores inseguros de producción al iniciar.

        @version 1.0
        @author Agustin
        """
        production = {
            "DJANGO_DEBUG": "False",
            "DJANGO_SECRET_KEY": "configuration-tests-only-0123456789-abcdefghij-ABCDEFGHIJ",
            "DJANGO_ALLOWED_HOSTS": "api.example.com",
        }
        for override, message in [
            ({"DJANGO_SECRET_KEY": ""}, "DJANGO_SECRET_KEY"),
            ({"DJANGO_SECRET_KEY": "short"}, "secure random key"),
            ({"DJANGO_SECRET_KEY": "a" * 60}, "secure random key"),
            ({"DJANGO_SECRET_KEY": "django-insecure-" + "abcdef" * 10}, "secure random key"),
            ({"DJANGO_ALLOWED_HOSTS": ""}, "DJANGO_ALLOWED_HOSTS"),
            ({"DJANGO_ALLOWED_HOSTS": "*"}, "DJANGO_ALLOWED_HOSTS"),
            ({"CORS_ALLOWED_ORIGINS": "http://portal.example.com"}, "must use HTTPS"),
            ({"CORS_ALLOWED_ORIGINS": "https://*.example.com"}, "without wildcards"),
            ({"CSRF_TRUSTED_ORIGINS": "http://portal.example.com"}, "must use HTTPS"),
            ({"CSRF_TRUSTED_ORIGINS": "https://*.example.com"}, "without wildcards"),
        ]:
            with self.subTest(override=override):
                result = self.load_settings(**(production | override))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_production_enables_https_and_trusts_proxy_only_when_configured(self):
        """Activa HTTPS y HSTS inicial sin extender la política a subdominios.

        @version 1.1
        @author Agustin
        """
        for trust_proxy in ("False", "True"):
            with self.subTest(trust_proxy=trust_proxy):
                result = self.load_settings(
                    DJANGO_DEBUG="False",
                    DJANGO_SECRET_KEY="configuration-tests-only-0123456789-abcdefghij-ABCDEFGHIJ",
                    DJANGO_ALLOWED_HOSTS="api.example.com",
                    DJANGO_TRUST_PROXY_HEADERS=trust_proxy,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                configuration = json.loads(result.stdout)
                self.assertFalse(configuration["DEBUG"])
                self.assertEqual(configuration["ALLOWED_HOSTS"], ["api.example.com"])
                self.assertEqual(configuration["CORS_ALLOWED_ORIGINS"], [])
                self.assertEqual(configuration["CSRF_TRUSTED_ORIGINS"], [])
                for name in ("SECURE_SSL_REDIRECT", "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE"):
                    self.assertTrue(configuration[name])
                self.assertEqual(configuration["SECURE_HSTS_SECONDS"], 3600)
                self.assertFalse(configuration["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
                self.assertFalse(configuration["SECURE_HSTS_PRELOAD"])
                self.assertEqual(configuration["DATABASES"]["default"]["OPTIONS"]["sslmode"], "require")
                self.assertEqual(
                    configuration["SECURE_PROXY_SSL_HEADER"],
                    ["HTTP_X_FORWARDED_PROTO", "https"] if trust_proxy == "True" else None,
                )

    def test_production_hsts_duration_can_be_overridden(self):
        """Permite ajustar HSTS o dejar de emitirlo mediante el entorno.

        @version 1.0
        """
        for seconds in (0, 86400):
            with self.subTest(seconds=seconds):
                result = self.load_settings(
                    DJANGO_DEBUG="False",
                    DJANGO_SECRET_KEY="configuration-tests-only-0123456789-abcdefghij-ABCDEFGHIJ",
                    DJANGO_ALLOWED_HOSTS="api.example.com",
                    DJANGO_SECURE_HSTS_SECONDS=str(seconds),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                configuration = json.loads(result.stdout)
                self.assertEqual(configuration["SECURE_HSTS_SECONDS"], seconds)
                self.assertFalse(configuration["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
                self.assertFalse(configuration["SECURE_HSTS_PRELOAD"])
