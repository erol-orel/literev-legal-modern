from django.urls import path
from django.http import HttpResponse
from literev.views import HomePageView, search, running, projectpage, generate_summary, tableselect, contentdocument

urlpatterns = [
    # enable these for celery
    path("status/", lambda request: HttpResponse("OK", status=200), name="status-view"),
    path('', HomePageView.as_view(), name='home'),
    path('search/', search, name='search'),
    path('running/', running, name='running'),
    path('project/<int:project_id>/', projectpage, name='projectpage'),
    path("tableselect/<int:project_id>/<int:refinement_id>/", tableselect, name="tableselect"),
    path('contentdocument/<int:document_id>', contentdocument, name='contentdocument'),
    path("generatesummary/<int:cluster_id>/", generate_summary, name="generate-summary"),
]
