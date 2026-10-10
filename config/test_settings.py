"""Django settings for the isolated Docker Compose test database."""

import os

from django.core.exceptions import ImproperlyConfigured


required = ("NEXUS_TEST_DB_NAME", "NEXUS_TEST_DB_USER", "NEXUS_TEST_DB_PASSWORD")
missing = [name for name in required if not os.getenv(name)]
if missing:
    raise ImproperlyConfigured(
        "Missing test database environment variables: " + ", ".join(missing)
    )

# Set these before importing the normal settings so neither the process environment
# nor .env can supply production database or Supabase credentials to test imports.
os.environ["NEXUS_SKIP_DOTENV"] = "1"
os.environ.update(
    DJANGO_SECRET_KEY="nexusback-tests-only-secret",
    POSTGRES_DB="nexusback-tests-only",
    POSTGRES_USER="nexusback-tests-only",
    DB_PASSWORD="nexusback-tests-only",
    POSTGRES_HOST="test-db",
    POSTGRES_PORT="5432",
    SUPABASE_URL="https://example.invalid",
    SUPABASE_KEY="nexusback-tests-only-anon-key",
    SUPABASE_SECRET_KEY="nexusback-tests-only-storage-key",
)

from .settings import *  # noqa: E402,F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["NEXUS_TEST_DB_NAME"],
        "USER": os.environ["NEXUS_TEST_DB_USER"],
        "PASSWORD": os.environ["NEXUS_TEST_DB_PASSWORD"],
        "HOST": "test-db",
        "PORT": "5432",
        "OPTIONS": {"sslmode": "disable"},
    }
}
