__version__ = "0.1.0"  # semantic-release
from .celery import app as celery_app

__all__ = ("celery_app",)
