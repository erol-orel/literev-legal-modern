from django.urls import path
from django.http import HttpResponse
from literev.views import run_task, run_pipeline_sample, HomePageView, search, running

urlpatterns = [
    # enable these for celery
#    path("status/", lambda request: HttpResponse("OK", status=200), name="status-view"),
#    path("task-sample/<int:number>/", run_task, name="run-task"),
    path("pipeline-sample/", run_pipeline_sample),
    path('', HomePageView.as_view(), name='home'),
    path('search/', search, name='search'),
    path('running/', running, name='running'),
]
