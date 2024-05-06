import logging
import os
import time

from pathlib import Path

import django
import typer

from django.conf import settings
from elasticsearch import Elasticsearch

from literev.libs.etl import DataLoader, DataReader

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()


app = typer.Typer()


class ElasticsearchManager:
    """
    Manages interactions with an Elasticsearch cluster, including health checks and data loading operations.

    Attributes
    ----------
    es_client : Elasticsearch
        An instance of the Elasticsearch client connected to an Elasticsearch cluster.

    Methods
    -------
    is_cluster_ready()
        Checks the health of the Elasticsearch cluster.
    load_data(file_path, index_name)
        Loads data from a JSONL file into the specified Elasticsearch index.
    """

    def __init__(self):
        """
        Initialize connections to the Elasticsearch cluster.

        Initializes the ElasticsearchManager with a connection to an Elasticsearch cluster
        using the settings from the Django settings module.
        """
        self.es_client = Elasticsearch(
            [settings.ES_HOST_URL],
            basic_auth=(settings.ES_USERNAME, settings.ES_PASSWORD),
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def is_cluster_ready(self) -> bool:
        """
        Check the cluster health and logs the status.

        Returns
        -------
        bool
            True if the cluster status is either green or yellow, False otherwise.
        """
        try:
            health = self.es_client.cluster.health()
            self.logger.info(f"Cluster Health: {health}")
            return health["status"] in ["green", "yellow"]
        except Exception as e:
            self.logger.error(f"Failed to retrieve cluster health due to: {e}")
            return False

    def load_data(self, file_path: Path, index_name: str) -> None:
        """
        Load data from a JSONL file into the specified Elasticsearch index.

        Parameters
        ----------
        file_path : Path
            The path to the JSONL file.
        index_name : str
            The name of the Elasticsearch index.

        Raises
        ------
        FileNotFoundError
            If the JSONL file does not exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"No JSONL file found at {file_path}.")

        self.logger.info(
            f"Loading data from {file_path} into {index_name} index..."
        )
        reader = DataReader(file_path=file_path)
        data_loader = DataLoader(reader)
        data_loader.load_into_es(
            es_client=self.es_client, index_name=index_name
        )
        self.logger.info("Data loaded into Elasticsearch successfully.")


@app.command()
def main(index_name: str, raw_jsonl: str, final_jsonl: str):
    """
    Execute the main function to load data into Elasticsearch.

    Parameters
    ----------
    index_name : str
        The Elasticsearch index name.
    raw_jsonl : str
        Path to the raw JSONL data file.
    final_jsonl : str
        Path to the final JSONL data file.
    """
    logging.basicConfig(level=logging.INFO)
    es_manager = ElasticsearchManager()
    attempts, max_retries = 0, 10
    while not es_manager.is_cluster_ready() and attempts < max_retries:
        logging.info("Waiting for the cluster to become ready...")
        time.sleep(30)
        attempts += 1

    if attempts == max_retries:
        logging.error("Max retries reached. Cluster is not ready. Exiting.")
        exit(1)

    # Ensure the final JSONL is prepared
    if not Path(final_jsonl).exists():
        logging.info("Preparing the JSONL file...")
        es_manager.load_data(file_path=Path(raw_jsonl), index_name=index_name)

    # Load data
    es_manager.load_data(file_path=Path(final_jsonl), index_name=index_name)


if __name__ == "__main__":
    app()
