from rest_framework.permissions import BasePermission


class IsProjectRAGOwner(BasePermission):
    """
    Custom permission to only allow owners of a project entry to access it.
    """

    def has_object_permission(self, request, view, obj):
        # For ProjectRAG and ProjectDocumentRAG, check if the user is the owner of the project
        return obj.project.user == request.user


class IsProjectRAGDocumentOwner(BasePermission):
    """
    Custom permission to only allow owners of a project entry to access it.
    """

    def has_object_permission(self, request, view, obj):
        # For ProjectRAG and ProjectDocumentRAG, check if the user is the owner of the project
        return obj.project_rag.project.user == request.user
