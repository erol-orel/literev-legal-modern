# type: ignore
# TODO: stop ignoring then use tasks
"""
This module shows some samples of how to compose a pipeline with celery tasks
"""

import datetime
import time

from celery import chain

from config.celery import app
from literev.libs.collectors import ElasticSearchCollector, MetaData


@app.task
def add_one_task(number: int) -> bool:
    """Simple example where number is added by 1.

    Usage: curl http://localhost:8000/task-sample/2/
    """
    print("Creating task")
    time.sleep(5)
    print(f"{number} + 1 = {number + 1}")
    return True


@app.task
def fetch_data(
    search: str, date_begin: datetime.date, date_end: datetime.date
) -> list[MetaData]:
    """Sample task to fetch data with collector returning a list of metadata"""
    print("Start fetching...")
    metadata = ElasticSearchCollector().collect_documents(
        search, date_begin, date_end
    )
    return metadata


@app.task
def process_data(metadata: list[MetaData]):
    """Sample task emulating the text processing"""
    print(f"Start Processing... {len(metadata)} documents.")
    print(metadata[0])
    print("Done!")


def run_pipeline(
    search: dict[str, str] = {
        "query": "divorce",
        "from": "2020-01-01",
        "to": "2021-01-01",
    },
):
    """
    Example of tasks composition.

    Usage:  curl http://localhost:8000/pipeline-sample/
    """
    job1 = fetch_data.signature(
        (
            search["query"],
            datetime.datetime.strptime(search["from"], "%Y-%m-%d"),
            datetime.datetime.strptime(search["to"], "%Y-%m-%d"),
        ),
    )

    job2 = process_data.signature()

    # chain is a sequece of tasks
    task = chain(
        job1,
        job2,  # receives the result of job1 as argument
    ).apply_async()

    # example: we can combine chains
    # task1 = chain(
    #     job1,
    #     job2, # will get the result of job1 as argument
    # )
    # task2 = chain(
    #     job3,
    #     job4,
    # )
    # task_of_chains = chain(task1.s(), task2.s())

    return task
