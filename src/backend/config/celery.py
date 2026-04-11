import os

from typing import Optional

import redis

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("literev-celery", include=["literev.tasks"])
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


def get_redis_client() -> redis.Redis:
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    if redis_url:
        return redis.from_url(redis_url)

    redis_host: str = os.getenv("REDIS_HOST", "literev-redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_username: Optional[str] = os.getenv("REDIS_USERNAME")
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD")

    return redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        username=redis_username,
        password=redis_password,
    )
