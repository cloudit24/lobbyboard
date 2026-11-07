"""LobbyBoard settings. Everything that differs per install comes from
environment variables (see .env.example); nothing about any organisation
lives in the code - names, logo, contact details and so on are entered in
the admin panel.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


DEBUG = env_bool("DEBUG", False)
# Signs logins and sessions: read only from .env, never written in the code.
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if len(SECRET_KEY) < 40 or SECRET_KEY.lower().startswith("change"):
    if not DEBUG:
        raise RuntimeError("Set SECRET_KEY in .env to a long random value (at least 40 characters). "
                           "Make one with: python -c \"import secrets; print(secrets.token_urlsafe(50))\"")
    # Development/tests only: a fresh random key each start (logins reset on restart).
    from django.core.management.utils import get_random_secret_key
    SECRET_KEY = get_random_secret_key()

# Django accepts any Host; core.network.AllowedHostsMiddleware checks it against
# these plus the addresses in Admin > Network settings (no restart needed).
ENV_ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "simple_history",
    "core",
    "library",
    "screens",
    "audit",
    "people",
    "visitors",
    "inbox",
    "desk",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.network.AllowedHostsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "audit.middleware.AuditMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context_processors.app_name",
        "core.context_processors.desk",
    ]},
}]

# SQLite in WAL mode: plenty for a handful of screens and agents, and it is
# one file to back up (DATA_DIR/db.sqlite3).
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": DATA_DIR / "db.sqlite3",
    "OPTIONS": {"init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
                "transaction_mode": "IMMEDIATE", "timeout": 20},
}}

# Shared by all Gunicorn workers, so weather/news are fetched once per refresh.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                      "LOCATION": DATA_DIR / "cache"}}
if "test" in sys.argv[1:2]:  # tests must not read or pollute the real cache
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
                    if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR / "media"

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "1024"))
FILE_UPLOAD_PERMISSIONS = 0o644

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APP_NAME = os.environ.get("APP_NAME", "LobbyBoard")

# Behind nginx / a tunnel: trust the forwarded scheme so CSRF works on https.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", False)
CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", False)
X_FRAME_OPTIONS = "SAMEORIGIN"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

# Locks stored stored secrets. Blank = worked out from
# SECRET_KEY, which means changing SECRET_KEY makes saved secrets unreadable.
FRONTDESK_ENCRYPTION_KEY = os.environ.get("FRONTDESK_ENCRYPTION_KEY", "")
