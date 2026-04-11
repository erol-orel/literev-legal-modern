from unittest.mock import MagicMock, patch

import pytest

from rest_framework.request import Request
from rest_framework.views import APIView

from literev.api.permissions import (
    IsProjectRAGDocumentOwner,
    IsProjectRAGOwner,
)


@pytest.fixture
def mock_request() -> Request:
    """Fixture to create a mock request object."""
    request = MagicMock(spec=Request)
    return request


@pytest.fixture
def mock_view() -> APIView:
    """Fixture to create a mock view object."""
    return MagicMock(spec=APIView)


@pytest.fixture
def mock_project_rag(user):
    """Fixture to create a mock ProjectRAG object."""
    project = MagicMock()
    project.id = 1
    project.user = user
    mock_project = MagicMock(project=project)
    mock_project.project.user = user
    return mock_project


@pytest.fixture
def mock_project_document_rag(mock_project_rag):
    """Fixture to create a mock ProjectDocumentRAG object."""
    return MagicMock(project_rag=mock_project_rag)


@pytest.mark.django_db
def test_is_project_rag_owner_allowed_for_owner(
    mock_request: Request, mock_view: APIView, mock_project_rag
):
    """Test that IsProjectRAGOwner allows access for project owner."""
    mock_request.user = mock_project_rag.project.user

    permission = IsProjectRAGOwner()
    result = permission.has_object_permission(
        mock_request, mock_view, mock_project_rag
    )

    assert result is True


@pytest.mark.django_db
def test_is_project_rag_owner_allowed_for_shared_user(
    mock_request: Request, mock_view: APIView, mock_project_rag, user
):
    """Test that IsProjectRAGOwner allows access for shared users."""
    with patch(
        "literev.api.permissions.get_shared_projects_ids",
        return_value=[mock_project_rag.project.id],
    ):
        permission = IsProjectRAGOwner()
        result = permission.has_object_permission(
            mock_request, mock_view, mock_project_rag
        )

    assert result is True


@pytest.mark.django_db
def test_is_project_rag_owner_denied(
    mock_request: Request, mock_view: APIView, mock_project_rag
):
    """Test that IsProjectRAGOwner denies access for unauthorized users."""
    mock_request.user = MagicMock()  # Different user

    with patch("literev.tasks.get_shared_projects_ids", return_value=[]):
        permission = IsProjectRAGOwner()
        result = permission.has_object_permission(
            mock_request, mock_view, mock_project_rag
        )

    assert result is False


@pytest.mark.django_db
def test_is_project_rag_document_owner_allowed(
    mock_request: Request, mock_view: APIView, mock_project_document_rag
):
    """
    Test that IsProjectRAGDocumentOwner.

    Check if IsProjectRAGDocumentOwner allows access for the document's project
    owner.
    """
    mock_request.user = mock_project_document_rag.project_rag.project.user

    permission = IsProjectRAGDocumentOwner()
    result = permission.has_object_permission(
        mock_request, mock_view, mock_project_document_rag
    )

    assert result is True


@pytest.mark.django_db
def test_is_project_rag_document_owner_denied(
    mock_request: Request, mock_view: APIView, mock_project_document_rag
):
    """
    Test IsProjectRAGDocumentOwner.

    Test if IsProjectRAGDocumentOwner denies access for unauthorized users.
    """
    mock_request.user = MagicMock()  # Different user

    permission = IsProjectRAGDocumentOwner()
    result = permission.has_object_permission(
        mock_request, mock_view, mock_project_document_rag
    )

    assert result is False
