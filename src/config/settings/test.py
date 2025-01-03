"""Settings for local testing."""

import os

from pathlib import Path

from dotenv import load_dotenv

PROJECT_PATH = Path(__file__).parent.parent.parent.parent

load_dotenv(PROJECT_PATH / ".env")
load_dotenv(PROJECT_PATH / "containers" / "literev" / ".env")

os.environ["POSTGRES_HOST"] = "localhost"
os.environ["RETSU_REDIS_HOST"] = "localhost"
os.environ["REDIS_HOST"] = "localhost"

from config.settings.dev import *  # noqa: F403

SERVICE_NAME = "literev-tests"

# CELERY
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
