from django.urls import path
from django.http import HttpResponse
from literev.views import run_task, run_pipeline_sample

urlpatterns = [
    path("status/", lambda request: HttpResponse("OK", status=200), name="status-view"),
    path("task-sample/<int:number>/", run_task, name="run-task"),
    path("pipeline-sample/", run_pipeline_sample),
]