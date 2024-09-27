import logging

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from literev.models import Cluster, Project


class Command(BaseCommand):
    help = "Fill order cluster in existing clusters"

    def handle(self, *args: Any, **options: Any) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.info("Starting to fill order field in Cluster object Model DB")

        try:
            UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"

            for project in Project.objects.all():
                clusters_in_project = Cluster.objects.filter(project=project)

                if not clusters_in_project:
                    continue
                grouped_clusters = clusters_in_project.annotate(
                    total_documents=Count("clusterelement__document"),
                ).order_by("-total_documents", "topic")

                index = 0
                for cluster in grouped_clusters:
                    if cluster.topic == UNCLASSIFIED_PAPERS_TOPIC:
                        continue
                    index += 1
                    cluster.order = index
                    cluster.save()

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            raise CommandError("Error during filling order in CLuster object")
