from django.urls import include, path
from django.http import HttpResponse
from literev.views import HomePageView, search, running, previousgraph, generate_summary, tableselect, contentdocument

urlpatterns = [
    # enable these for celery
    path("status/", lambda request: HttpResponse("OK", status=200), name="status-view"),
    path("accounts/", include("allauth.urls")),
    path('', HomePageView.as_view(), name='home'),
    path('search/', search, name='search'),
    path('running/', running, name='running'),
    path('previousgraph/', previousgraph, name='previousgraph'),
    path('tableselect/', tableselect, name='tableselect'),
    path('contentdocument/<int:document_id>', contentdocument, name='contentdocument'),
    path("generatesummary/<int:cluster_id>/", generate_summary, name="generate-summary"),
]
