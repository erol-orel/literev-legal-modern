import logging
import os
import time

from pathlib import Path

import typer

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

from literev.libs.etl import DataLoader, DataReader

env_dir = Path(__file__).resolve().parent.parent
load_dotenv(env_dir / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()

ES_HOST_URL = os.getenv("ES_HOST_URL", "http://localhost:9200")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "")
ES_CERTIF = os.getenv("ES_CERTIF", "")


def create_es_client() -> Elasticsearch:
    """Create an Elasticsearch client using environment credentials."""
    return Elasticsearch(
        [ES_HOST_URL],
        basic_auth=(ES_USERNAME, ES_PASSWORD),
        verify_certs=False,
    )


def is_cluster_ready(es_client, retries=3, delay=30) -> bool:
    """Check if Elasticsearch cluster is ready."""
    for attempt in range(retries):
        try:
            health = es_client.cluster.health()
            logger.info(f"Cluster Health: {health}")
            if health["status"] in ["green", "yellow"]:
                return True
        except Exception as e:
            logger.error(f"Failed to retrieve cluster health: {e}")
        logger.info(f"Retrying... ({attempt + 1}/{retries})")
        time.sleep(delay)
    return False


def get_total_documents_in_index(es: Elasticsearch, index_name: str) -> int:
    """Return the total number of documents in an Elasticsearch index."""
    response = es.count(index=index_name, body={"query": {"match_all": {}}})
    return response["count"]


@app.command()
def load_data(
    index_to_load: str = typer.Option(
        ..., "--index-name", "-i", help="Elasticsearch index to load data into"
    ),
    raw_json: Path = typer.Option(
        ..., "--raw-json", "-r", help="Path to the raw JSON file"
    ),
    final_json: Path = typer.Option(
        None, "--final-json", "-f", help="Path to the parsed JSON file"
    ),
):
    """
    Load data into an Elasticsearch index. Always parse JSON if final_json is not provided.

    Parameters
    ----------
    index_to_load : str
        The Elasticsearch index where data will be loaded.
    raw_json : Path
        Path to the raw JSON file.
    final_json : Path, optional
        Path to the parsed JSON file. If not provided, parsed from raw_json.
    """
    es_client = create_es_client()

    if not is_cluster_ready(es_client):
        logger.error("Cluster is not ready. Exiting.")
        raise typer.Exit(code=1)

    if not raw_json.exists():
        logger.error(f"JSON file not found at {raw_json}. Exiting.")
        raise typer.Exit(code=1)

    # TODO: Check if the document count in raw and final JSON files matches
    # in case of any failure to ensure data consistency.
    if index_to_load in str(final_json) and not final_json.exists():
        logger.info(
            f"Provided final JSON file does not exist at {final_json}."
        )
        logger.info("Parsing raw JSON to final JSON...")
        final_json = final_json or raw_json.with_suffix(".parsed.json")
        reader = DataReader(file_path=raw_json)
        data_loader = DataLoader(reader)
        data_loader.load_into_json_file(export_path=final_json)
        logger.info(f"JSON file parsed and saved to {final_json}.")
    else:
        logger.info(f"Using existing final JSON file: {final_json}")

    logger.info(
        f"Loading data from {final_json} into Elasticsearch index: {index_to_load}"
    )
    reader = DataReader(file_path=final_json)
    data_loader = DataLoader(reader)
    data_loader.load_into_es(
        es_client=es_client, index_name=index_to_load, file_path=str(raw_json)
    )
    logger.info("Data loaded successfully.")


@app.command()
def count_documents(
    index_name: str = typer.Argument(
        ..., help="The name of the Elasticsearch index to query."
    ),
):
    """Retrieve and print the total number of documents in the specified Elasticsearch index."""
    es_client = create_es_client()
    total_docs = get_total_documents_in_index(es_client, index_name)
    typer.echo(f"Total documents in '{index_name}' index: {total_docs}")


if __name__ == "__main__":
    app()
