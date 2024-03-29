import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery("literev-celery")

# namespace means all celery settings will be prepended by CELERY_
# example: CELERY_BROKER
app.config_from_object("django.conf:settings", namespace="CELERY")

# tells Celery to look for Celery tasks from
# applications defined in settings.INSTALLED_APPS
app.autodiscover_tasks()
