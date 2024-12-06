from rest_framework.permissions import BasePermission

from literev.tasks import get_shared_projects_ids


class IsProjectRAGOwner(BasePermission):
    """
    Custom permission to only allow owners of a project entry to access it.
    """

    def has_object_permission(
        self, request, obj
    ):  # removed `view` input variable because linter
        # For ProjectRAG and ProjectDocumentRAG, check if the user is the owner of the project
        return (
            obj.project.id in get_shared_projects_ids()
            or obj.project.user == request.user
        )


class IsProjectRAGDocumentOwner(BasePermission):
    """
    Custom permission to only allow owners of a project entry to access it.
    """

    def has_object_permission(
        self, request, obj
    ):  # removed `view` variable because linter
        # For ProjectRAG and ProjectDocumentRAG, check if the user is the owner of the project
        return obj.project_rag.project.user == request.user
