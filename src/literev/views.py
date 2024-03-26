from django.http import JsonResponse
from tasks.sample_tasks import add_one_task, run_pipeline


def run_task(request, number):
    if number:
        task = add_one_task.delay(number)
        return JsonResponse({"task_id": task.id}, status=202)


def run_pipeline_sample(request):
    task = run_pipeline()
    return JsonResponse({"task_id": task.id}, status=202)
