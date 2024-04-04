import logging

from typing import Any, Dict

from django.conf import settings
from django.http import HttpRequest

from config import __version__


def settings_context(request: HttpRequest) -> Dict[str, Any]:
    """Settings available by default to the templates context."""
    # note: resolve issues with vulture and ruff
    logging.info(request)
    # Note: intentionally do NOT expose the entire settings
    # to prevent accidental leaking of sensitive information
    context = {
        "DEBUG": settings.DEBUG,
        "VERSION": __version__,
    }

    return context
