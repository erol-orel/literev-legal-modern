from django.http import HttpResponse
from django.urls import URLPattern, URLResolver, include, path
from rest_framework.routers import DefaultRouter

from literev.api import project_lists as project_lists_api
from literev.api import document_content as document_content_api
from literev.api import project_overview as project_overview_api
from literev.api import rag_workspace as rag_workspace_api
from literev.api import search as search_api
from literev.api import table_selection as table_selection_api
from literev.api import views as views_api
from literev.views_public import (
    authenticated_frontend_app,
    home_frontend_app,
    public_frontend_app,
)

URL = URLPattern | URLResolver

router = DefaultRouter()
router.register(
    r"project-rags", views_api.ProjectRAGViewSet, basename="projectrag"
)
router.register(
    r"project-documents-rag",
    views_api.ProjectDocumentRAGViewSet,
    basename="projectdocumentsrag",
)

api_urlpatterns: list[URL] = [
    path(r"", include(router.urls)),
    path(
        "search/convert-query/",
        search_api.ConvertToBooleanQueryAPIView.as_view(),
        name="api-search-convert-query",
    ),
    path(
        "search/validate/",
        search_api.SearchValidationAPIView.as_view(),
        name="api-search-validate",
    ),
    path(
        "search/preview/",
        search_api.SearchPreviewAPIView.as_view(),
        name="api-search-preview",
    ),
    path(
        "search/projects/",
        search_api.SearchProjectAPIView.as_view(),
        name="api-search-projects",
    ),
    path(
        "running/",
        project_lists_api.RunningProjectsAPIView.as_view(),
        name="api-running-projects",
    ),
    path(
        "running/<int:project_id>/restart/",
        project_lists_api.RunningProjectRestartAPIView.as_view(),
        name="api-running-project-restart",
    ),
    path(
        "projects/<int:project_id>/",
        project_lists_api.ProjectDeleteAPIView.as_view(),
        name="api-project-delete",
    ),
    path(
        "projects/<int:project_id>/overview/",
        project_overview_api.ProjectOverviewAPIView.as_view(),
        name="api-project-overview",
    ),
    path(
        "projects/<int:project_id>/filters/preview/",
        project_overview_api.ProjectFilterPreviewAPIView.as_view(),
        name="api-project-filter-preview",
    ),
    path(
        "projects/<int:project_id>/refinements/",
        project_overview_api.ProjectRefinementsAPIView.as_view(),
        name="api-project-refinements",
    ),
    path(
        "projects/<int:project_id>/refinements/<int:refinement_id>/",
        project_overview_api.ProjectRefinementDetailAPIView.as_view(),
        name="api-project-refinement-detail",
    ),
    path(
        "projects/<int:project_id>/clusters/<int:cluster_id>/summary/",
        project_overview_api.ProjectClusterSummaryAPIView.as_view(),
        name="api-project-cluster-summary",
    ),
    path(
        "projects/<int:project_id>/ask-top-docs/",
        project_overview_api.ProjectAskTopDocumentsAPIView.as_view(),
        name="api-project-ask-top-docs",
    ),
    path(
        "rag/<int:project_id>/context/",
        rag_workspace_api.RagContextAPIView.as_view(),
        name="api-rag-context",
    ),
    path(
        "rag/<int:project_id>/context/<int:rag_id>/",
        rag_workspace_api.RagContextAPIView.as_view(),
        name="api-rag-context-detail",
    ),
    path(
        "rag/<int:project_id>/<int:rag_id>/report.docx/",
        rag_workspace_api.RagReportDocxAPIView.as_view(),
        name="api-rag-report-docx",
    ),
    path(
        "rag/<int:project_id>/<int:rag_id>/",
        rag_workspace_api.RagDeleteAPIView.as_view(),
        name="api-rag-delete",
    ),
    path(
        "documents/<int:document_id>/",
        document_content_api.DocumentContentAPIView.as_view(),
        name="api-document-content",
    ),
    path(
        "documents/rag/<int:document_rag_id>/highlighted/",
        document_content_api.HighlightedDocumentContentAPIView.as_view(),
        name="api-document-content-highlighted",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/state/",
        table_selection_api.TableSelectionStateAPIView.as_view(),
        name="api-tableselect-state",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/selection/",
        table_selection_api.TableSelectionUpdateAPIView.as_view(),
        name="api-tableselect-selection",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/iterations/<int:iteration_id>/activate/",
        table_selection_api.TableSelectionIterationActivateAPIView.as_view(),
        name="api-tableselect-iteration-activate",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/iterations/<int:iteration_id>/",
        table_selection_api.TableSelectionIterationDetailAPIView.as_view(),
        name="api-tableselect-iteration-detail",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/iterate/",
        table_selection_api.TableSelectionIterateAPIView.as_view(),
        name="api-tableselect-iterate",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/reset/",
        table_selection_api.TableSelectionResetAPIView.as_view(),
        name="api-tableselect-reset",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/check-all/",
        table_selection_api.TableSelectionCheckAllAPIView.as_view(),
        name="api-tableselect-check-all",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/export/",
        table_selection_api.TableSelectionExportAPIView.as_view(),
        name="api-tableselect-export",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/ask-selected/",
        table_selection_api.TableSelectionAskSelectedAPIView.as_view(),
        name="api-tableselect-ask-selected",
    ),
    path(
        "historical/",
        project_lists_api.HistoricalProjectsAPIView.as_view(),
        name="api-historical-projects",
    ),
    path(
        "historical/delete-all/",
        project_lists_api.HistoricalProjectsDeleteAllAPIView.as_view(),
        name="api-historical-delete-all",
    ),
]


urlpatterns: list[URL] = [
    path(
        "status/",
        lambda request: HttpResponse("OK", status=200),
        name="status-view",
    ),
    path("", home_frontend_app, name="home"),
    path("search/", authenticated_frontend_app, name="search"),
    path("running/", authenticated_frontend_app, name="running"),
    path("historicalpage/", authenticated_frontend_app, name="historicalpage"),
    path(
        "project/<int:project_id>/",
        authenticated_frontend_app,
        name="projectpage",
    ),
    path(
        (
            "tableselect/<int:project_id>/<int:refinement_id>/"
            "<int:iteration_id>/page=<int:num>/order_by=<str:order_by>/"
        ),
        authenticated_frontend_app,
        name="tableselect",
    ),
    path(
        "tableselect/<int:project_id>/<int:refinement_id>/",
        authenticated_frontend_app,
        name="tableselect-default",
    ),
    path(
        "contentdocument/<int:document_id>",
        authenticated_frontend_app,
        name="contentdocument",
    ),
    path(
        "contentdocument_highlighted/<int:document_rag_id>/",
        authenticated_frontend_app,
        name="contentdocument_highlighted",
    ),
    path(
        "rag/<int:project_id>/",
        authenticated_frontend_app,
        name="project-rag-page",
    ),
    path(
        "rag/<int:project_id>/<int:rag_id>",
        authenticated_frontend_app,
        name="project-rag-id-page",
    ),
    path(
        "api/project-rags-by-project/<int:project_id>/<int:rag_id>/",
        views_api.ProjectRAGbyProjectIdAPIView.as_view(),
        name="projectrag-by-project-rag-id",
    ),
    path(
        "api/project-rags-by-project/<int:project_id>/",
        views_api.ProjectRAGbyProjectIdAPIView.as_view(),
        name="projectrag-by-project",
    ),
    path("product/", public_frontend_app, name="product"),
    path("company/", public_frontend_app, name="company"),
    path("blog/", public_frontend_app, name="blog"),
    path("team/", public_frontend_app, name="team"),
]
