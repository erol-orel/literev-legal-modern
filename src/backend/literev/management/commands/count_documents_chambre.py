import logging
import time

from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from literev.libs.collectors import ElasticSearchCollector

CHAMBER_NAMES = settings.LITEREV_CHAMBER_NAMES

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Command(BaseCommand):
    help = "count chambre for given index"

    def add_arguments(self, parser):
        parser.add_argument(
            "--index-name",
            type=str,
            required=True,
            help="The name of the legal chamber.",
        )

    def handle(
        self, *args, **options
    ) -> None:  # removed *args: Any, **options: Any because linter
        index_name = options["index_name"]

        start_time = time.time()

        if index_name == "test":
            start_date = datetime(2023, 6, 1)
            end_date = datetime(2023, 6, 10)

            search_query = "police AND fils"

            collector = ElasticSearchCollector(index_name="chambre_penale")

            documents = collector.collect_documents(
                search_query, start_date, end_date
            )

        else:
            if index_name not in CHAMBER_NAMES:
                logging.error(
                    f"index_name must be one of the following: {CHAMBER_NAMES}"
                )
                raise

            collector = ElasticSearchCollector(index_name=index_name)
            documents = collector.collect_all_documents()

        counter_chamber = {}

        for document in documents:
            chamber = getattr(document, "chamber")
            if chamber not in counter_chamber:
                counter_chamber[chamber] = 0

            counter_chamber[chamber] += 1

        print(counter_chamber)

        end_time = time.time()

        total_time = (end_time - start_time) / 60

        logging.info(f"Elapsed time {total_time} min")
        print(f"\nElapsed time {total_time} min")
