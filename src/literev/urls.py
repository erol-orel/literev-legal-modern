from django.urls import path, include
from django.http import HttpResponse
from literev.views import HomePageView, search, running, projectpage, generate_summary, tableselect, contentdocument, historicalpage, rag

from rest_framework.routers import DefaultRouter
from literev.api import views as views_api

router = DefaultRouter()
router.register(r'project-rags', views_api.ProjectRAGViewSet, basename='projectrag')
router.register(r'project-documents-rag', views_api.ProjectDocumentRAGViewSet, basename='projectdocumentsrag')
# router.register(r'project', views_api.ProjectViewSet, basename='project')

api_urlpatterns = [
    path(r"", include(router.urls)),
]


urlpatterns = [
    # enable these for celery
    path("status/", lambda request: HttpResponse("OK", status=200), name="status-view"),
    path('', HomePageView.as_view(), name='home'),
    path('search/', search, name='search'),
    path('running/', running, name='running'),
    path('historicalpage/', historicalpage, name='historicalpage'),
    path('project/<int:project_id>/', projectpage, name='projectpage'),
    path("tableselect/<int:project_id>/<int:refinement_id>/<int:iteration_id>/page=<int:num>/order_by=<str:order_by>/", tableselect, name="tableselect"),
    path("tableselect/<int:project_id>/<int:refinement_id>/", tableselect, name="tableselect-default"),
    path('contentdocument/<int:document_id>', contentdocument, name='contentdocument'),
    path("generatesummary/<int:cluster_id>/", generate_summary, name="generate-summary"),
    path("rag/<int:project_id>/", rag, name="project-rag-page"),
    path("api/project-rags-by-project/<int:project_id>/", views_api.ProjectRAGbyProjectIdAPIView.as_view(), name="projectrag-by-project"),
    path(("project/<int:project_id>/tablechoice/iteration/<int:iteration_id>/page/<int:page>/"), views_api.UpdateTableChoiceAPIView.as_view(), name="update-table-choice",),
]
