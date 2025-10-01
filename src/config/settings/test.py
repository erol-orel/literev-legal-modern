"""Settings for local testing."""

import os

from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

project_path = Path(__file__).resolve().parents[3]
load_dotenv(project_path / ".env")
load_dotenv(project_path / "containers" / "literev" / ".env")

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "0")
os.environ.setdefault("REDIS_USERNAME", "app")

password_file = project_path / "containers" / "redis" / "config" / "redis.pass"
if not os.getenv("REDIS_PASSWORD") and password_file.exists():
    os.environ["REDIS_PASSWORD"] = password_file.read_text().strip()

redis_host: str = os.getenv("REDIS_HOST", "localhost")
redis_port: str = os.getenv("REDIS_PORT", "6379")
redis_db: str = os.getenv("REDIS_DB", "0")
redis_username: str = os.getenv("REDIS_USERNAME", "app")
redis_password: str = os.getenv("REDIS_PASSWORD", "")

redis_username_encoded: str = quote(redis_username, safe="")
redis_password_encoded: str = quote(redis_password, safe="")

redis_url: str = (
    f"redis://{redis_username_encoded}:{redis_password_encoded}"
    f"@{redis_host}:{redis_port}/{redis_db}"
)

os.environ["REDIS_URL"] = redis_url

# Always use in-memory broker/backend for Celery in tests
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"

from config.settings.dev import *  # noqa: F403

SERVICE_NAME = "literev-tests"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
