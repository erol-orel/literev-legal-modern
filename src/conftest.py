"""Pytest configuration."""

from __future__ import annotations

import datetime
import logging

from typing import Any, Generator

import pytest

from celery.contrib.testing.worker import start_worker
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from config.celery import app as celery_app
from literev.models import Document, Project


def redis_flush() -> None:
    """Wipe-out redis database."""
    from config.celery import get_redis_client

    redis_client = get_redis_client()
    redis_client.flushdb()


@pytest.fixture
def user(db) -> User:
    """Fixture to create a sample user."""
    return User.objects.create_user(
        username="testuser@test.com", password="testpassword"
    )


@pytest.fixture
def project(user):
    """Fixture for a sample project."""
    return Project.objects.create(
        user=user,
        name="Sample Project",
        creation_date=datetime.date(2023, 1, 1),
        query="Sample query",
        range_begin_date=datetime.date(2022, 1, 1),
        range_end_date=datetime.date(2022, 12, 31),
        total_documents=100,
        selected_indices=[1, 2, 3],
        step="processing",
        step_number=3,
        is_finish=False,
        is_running=True,
        best_dbcv=0.85,
        actual_task_code="task_code_sample",
    )


@pytest.fixture
def document(project):
    """Fixture for a sample document."""
    return Document.objects.create(
        project=project,
        decision_type="Decision Type Sample",
        decision_date=datetime.date(2023, 5, 15),
        procedure_type="Procedure Type Sample",
        descriptors="Sample descriptors for the document",
        standards="Standard 1, Standard 2",
        result="Accepted",
        raw_document_id="DOC12345",
        raw_document_text="This is the raw text of the document.",
        prepared_for_ngrams="prepared sample n-grams",
        preprocessed_document="Preprocessed document text.",
        procedure_year=datetime.date(2023, 1, 1),
    )


@pytest.fixture
def api_client() -> APIClient:
    client = APIClient()
    return client


@pytest.fixture
def authenticated_api_client(api_client: APIClient, user: User) -> APIClient:
    """Authenticate the API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture(scope="session")
def celery_worker_parameters() -> dict[str, Any]:
    """Parameters for the Celery worker."""
    return {
        "loglevel": "debug",  # Set log level
        "concurrency": 4,  # Number of concurrent workers
        "perform_ping_check": False,
        "pool": "prefork",
    }


@pytest.fixture(autouse=True, scope="session")
def setup(
    celery_worker_parameters: dict[str, Any],
) -> Generator[None, None, None]:
    """Set up the services needed by the tests."""
    try:
        logging.info("Clean Redis queues")
        redis_flush()

        logging.info("Start the Celery worker")
        with start_worker(celery_app, **celery_worker_parameters) as worker:
            yield worker

    finally:
        pass
