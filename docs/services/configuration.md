# Configuration & Environment

All application configuration is managed through environment variables loaded from a `.env` file. Never hardcode secrets or environment-specific values in source code.

Source files:
- Base settings: [src/config/settings/base.py](../../src/config/settings/base.py)
- Dev settings: [src/config/settings/dev.py](../../src/config/settings/dev.py)
- Test settings: [src/config/settings/test.py](../../src/config/settings/test.py)
- Prod settings: [src/config/settings/prod.py](../../src/config/settings/prod.py)

---

## Settings Modules

Select the active module via `DJANGO_SETTINGS_MODULE`:

| Module | `DJANGO_SETTINGS_MODULE` value | Use case |
|---|---|---|
| base | (never used directly) | Shared settings inherited by all |
| dev | `config.settings.dev` | Local development |
| test | `config.settings.test` | pytest runs |
| prod | `config.settings.prod` | Production deployment |

The `.env` file should contain:
```
DJANGO_SETTINGS_MODULE=config.settings.dev
```

---

## Environment Variables Reference

### System

| Variable | Required | Example | Description |
|---|---|---|---|
| `ENV` | no | `dev` / `prod` | Environment label (used in logs) |
| `DEBUG` | yes | `True` / `False` | Django debug mode |
| `DJANGO_SECRET_KEY` | yes | `django-insecure-...` | Django secret key — must be long random string in prod |
| `ALLOWED_HOSTS` | yes | `literev.example.com,localhost` | Comma-separated allowed hostnames |
| `DJANGO_SETTINGS_MODULE` | yes | `config.settings.dev` | Active settings module |
| `USE_CONTAINER` | no | `true` | Whether running inside Docker |
| `HOST_UID` / `HOST_GID` | Docker only | `1000` | User/group IDs for volume permissions |

### Database (PostgreSQL)

Two sets of credentials are used:

| Variable | Description |
|---|---|
| `POSTGRES_HOST` | Database hostname (e.g. `literev-postgres`) |
| `POSTGRES_PORT` | Database port (default: `5432`) |
| `POSTGRES_DB` | Database name (e.g. `literev`) |
| `POSTGRES_USER` | Application user (limited privileges) |
| `POSTGRES_PASSWORD` | Application user password |
| `POSTGRES_ADMIN_USER` | Admin user (`postgres`) — used only for migrations and setup |
| `POSTGRES_ADMIN_PASSWORD` | Admin user password |

The dual-credential setup follows least-privilege principles: the running application uses a restricted user, while admin operations use the `postgres` superuser.

### Redis

| Variable | Description |
|---|---|
| `REDIS_HOST` | Redis hostname (e.g. `literev-redis`) |
| `REDIS_PORT` | Redis port (default: `6379`) |
| `REDIS_DB` | Database index (default: `0`) |
| `REDIS_URL` | Full Redis URL — overrides HOST/PORT/DB if set |
| `REDIS_USERNAME` | Redis ACL username |
| `REDIS_PASSWORD` | Redis ACL password |

### Elasticsearch

| Variable | Description |
|---|---|
| `ES_HOST_URL` | Elasticsearch URL (e.g. `https://es.example.com:9200`) |
| `ES_USERNAME` | Elasticsearch username |
| `ES_PASSWORD` | Elasticsearch password |
| `ES_INDEX_NAME` | Default index name |

### LLM APIs

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | yes (if not using Hactar) | OpenAI API key |
| `USE_HACTAR_LLM` | no | `true` to use Hactar/Ollama instead of OpenAI |
| `HACTAR_API_KEY` | if Hactar | Hactar API authentication key |
| `HACTAR_VERIFY_SSL` | no | `true` (default) to verify SSL for Hactar endpoint |

### File Paths

| Variable | Description |
|---|---|
| `CONTAINER_VOLUME_DATA_DIR` | Base data directory (e.g. `/opt/data/literev`) |
| `STATIC_ROOT` | Django static files directory |
| `MEDIA_ROOT` | Django media files directory |
| `LITEREV_CACHE_DIR` | RAG file cache directory (retrieval, embedding, generation caches) |

### Performance

| Variable | Default | Description |
|---|---|---|
| `NUMBER_THREADS_ALLOWED` | `4` | Worker pool size for NLP multiprocessing and Celery workers |
| `NUMBER_TRIALS` | `50` | Number of Optuna hyperparameter search trials |
| `NUMBER_OPTUNA_JOBS` | `4` | Parallel Optuna workers |

### Web / Security

| Variable | Description |
|---|---|
| `FRONTEND_HOST_PORT` | Port for the Django app (e.g. `8000`) |
| `CERTBOT_DOMAIN` | Domain for Let's Encrypt SSL certificate |
| `CERTBOT_EMAIL` | Email for Let's Encrypt notifications |

### Monitoring

| Variable | Description |
|---|---|
| `SENTRY_DSN` | Sentry error tracking DSN (production only) |
| `LOGGING_LEVEL` | Log level: `INFO` or `DEBUG` |

---

## Settings Module Details

### base.py

Contains all shared configuration:

```python
SERVICE_NAME = "literev"
INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "rest_framework",
    "django_filters",
    # Local
    "literev",
]

# Authentication
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SITE_ID = 1
LOGIN_REDIRECT_URL = "/"
ACCOUNT_EMAIL_REQUIRED = True

# REST Framework defaults
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}
```

### dev.py

Extends `base.py` for local development:

```python
DEBUG = True

INSTALLED_APPS += [
    "debug_toolbar",
    "django_extensions",
]

MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Faster password hashing for tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
```

### test.py

Extends `dev.py` for pytest:

```python
# In-memory or test database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_literev",
        # ... test credentials
    }
}

# Disable Celery for unit tests (use .apply() directly)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

### prod.py

Extends `base.py` for production:

```python
DEBUG = False

# Security hardening
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Error tracking
import sentry_sdk
sentry_sdk.init(dsn=SENTRY_DSN, ...)

# Email (for allauth account emails)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = ...
```

---

## Setting Up Your `.env` File

Copy the template below, fill in required values, and save as `.env` at the project root. Never commit this file to git (it is in `.gitignore`).

```bash
cp .env.tpl .env
```

**Full template:**

```env
# System / Host
HOST_UID=1001
HOST_GID=1001
USE_CONTAINER=True

# Runtime / Django
ENV=dev
DEBUG=True
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY='django-insecure-change-this-in-production'
ALLOWED_HOSTS='localhost'
GUNICORN_WORKERS=1
FRONTEND_HOST_PORT=8000

# Resources
DOCKER_CPU_LIMIT=1.0
DOCKER_CPU_RESERVATION=0.5

# Paths
CONTAINER_VOLUME_DATA_DIR=/opt/data/literev
STATIC_ROOT=/opt/data/literev/static
MEDIA_ROOT=/opt/data/literev/static/media
POSTGRES_DATA=/opt/data/literev/postgres

# Postgres
POSTGRES_HOST=literev-postgres
POSTGRES_PORT=35432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB_LITEREV=literev
POSTGRES_USER_LITEREV=literev
POSTGRES_PASSWORD_LITEREV=change-this-password

# Elasticsearch
ES_HOST_URL=http://localhost:9200/
ES_USERNAME=elastic
ES_PASSWORD=change-this-password
ES_SSL_CERTS=False

# Redis
REDIS_HOST=literev-redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=""

# Certbot / Nginx
CERTBOT_DOMAIN=myapp.domain.com
CERTBOT_EMAIL=myapp@gmail.com
CERTBOT_CONF=./containers/nginx/data/certbot/conf
CERTBOT_WWW=./containers/nginx/data/certbot/www
NGNIX_CONF=./containers/nginx/data/config/prod

# Integrations
OPENAI_API_KEY=sk-...

# App tuning
NUMBER_ARTICLE_BY_PAGE=30
NUMBER_THREADS_ALLOWED=4
NUMBER_TRIALS=20
UPDATE_INTERVAL=2700000
```

**Minimum required variables for local development (without containers):**

```bash
DJANGO_SETTINGS_MODULE=config.settings.dev
DEBUG=True
DJANGO_SECRET_KEY=django-insecure-local-dev-key-change-in-prod
ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=literev
POSTGRES_USER=literev
POSTGRES_PASSWORD=literev
POSTGRES_ADMIN_USER=postgres
POSTGRES_ADMIN_PASSWORD=postgres

REDIS_HOST=localhost
REDIS_PORT=6379

ES_HOST_URL=http://localhost:9200
ES_INDEX_NAME=literev

OPENAI_API_KEY=sk-...

LITEREV_CACHE_DIR=/tmp/literev-cache
NUMBER_THREADS_ALLOWED=4
NUMBER_TRIALS=20
NUMBER_OPTUNA_JOBS=2
```

---

## Per-Service `.env` Files (Optional)

If you prefer to keep per-service env files, start from their templates.

`./containers/literev/.env` (Django service inside the container):

```env
DJANGO_SETTINGS_MODULE=config.settings.dev
ALLOWED_HOSTS=localhost
DB_HOST=literev-postgres
DB_NAME=literev
DB_USER=literev
DB_PASSWORD=change-this-password
MEDIA_ROOT=/opt/data/literev/static/media
GUNICORN_WORKERS=1
```

`./containers/postgresql/.env` (Postgres service):

```env
POSTGRES_PORT=35432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

---

## Docker Compose Environment

When running via Docker (`makim containers.start`), the `.env` file is automatically loaded by Docker Compose:

```yaml
# docker-compose.dev.yaml
services:
  literev:
    env_file: .env
    environment:
      USE_CONTAINER: "true"
      POSTGRES_HOST: literev-postgres   # override to Docker service name
      REDIS_HOST: literev-redis
```

Container-specific overrides (like `POSTGRES_HOST`) are set in the compose file and take precedence over `.env`.

---

## Configuration Validation

Django will raise `ImproperlyConfigured` at startup if required settings are missing. The pattern used:

```python
import os
from django.core.exceptions import ImproperlyConfigured

def get_env_var(var_name: str, default=None) -> str:
    value = os.environ.get(var_name, default)
    if value is None:
        raise ImproperlyConfigured(f"Set the {var_name} environment variable")
    return value

SECRET_KEY = get_env_var("DJANGO_SECRET_KEY")
```
