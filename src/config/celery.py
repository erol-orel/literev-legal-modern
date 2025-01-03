"""Celery app configuration."""

import os

import redis

from celery import Celery

redis_host_default = "literev-redis"
redis_host: str = os.getenv("REDIS_HOST", redis_host_default)
redis_port: int = int(os.getenv("REDIS_PORT", 6379))
redis_db: int = int(os.getenv("REDIS_DB", 0))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
app = Celery(
    "literev-celery",
    include=[
        "literev.tasks",
    ],
)

# namespace means all celery settings will be prepended by CELERY_
# example: CELERY_BROKER
app.config_from_object("django.conf:settings", namespace="CELERY")

# tells Celery to look for Celery tasks from
# applications defined in settings.INSTALLED_APPS
app.autodiscover_tasks()


def get_redis_client() -> redis.Redis:
    return redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        ssl=False,
    )
