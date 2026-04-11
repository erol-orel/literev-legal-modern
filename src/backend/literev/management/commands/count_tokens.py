import logging

from typing import List, Tuple

import psycopg2
import tiktoken

from django.core.management.base import BaseCommand
from psycopg2 import OperationalError

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

GPT_MODEL = "gpt-4o-mini"
enc = tiktoken.encoding_for_model(GPT_MODEL)


def get_data(project_id: int) -> List[Tuple[int, int, str]]:
    """
    Retrieve all documents related to a specific project ID from the database.

    Parameters
    ----------
    project_id : int
        The project ID for which to query documents.

    Returns
    -------
    list
        A list of tuples containing the document data (id, raw_document_id, text).

    Raises
    ------
    OperationalError
        If a database connection error occurs.
    Exception
        For other issues that may arise when executing the query.
    """
    from django.conf import (
        settings,
    )  # Import inside the function for Django settings

    database_uri = settings.DATABASE_URI
    try:
        conn = psycopg2.connect(database_uri)
        cursor = conn.cursor()
        query = """
            SELECT id, raw_document_id, raw_document_text
            FROM public.literev_document
            WHERE project_id = %s;
        """
        cursor.execute(query, (project_id,))
        data = cursor.fetchall()
        conn.close()
        logger.info(
            f"Retrieved {len(data)} documents for project ID {project_id}."
        )
        return data
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        raise


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a given text using the model's tokenizer.

    Parameters
    ----------
    text : str
        The input text to tokenize.

    Returns
    -------
    int
        The token count of the text.
    """
    return len(enc.encode(text))


class Command(BaseCommand):
    help = "Analyze documents for a given project ID and display token statistics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id",
            type=int,
            required=True,
            help="The ID of the project to analyze.",
        )

    def handle(self, *args, **options):
        project_id = options["project_id"]
        try:
            logger.info("Starting analysis...")
            project_data = get_data(project_id)

            if not project_data:
                self.stdout.write(
                    self.style.WARNING(
                        f"No documents found for project ID {project_id}."
                    )
                )
                return

            # Filter and process data
            tokens = [
                count_tokens(doc[2])
                for doc in project_data
                if doc[2] and doc[2].strip()
            ]

            if not tokens:
                self.stdout.write(
                    self.style.WARNING(
                        f"No valid documents with text for project ID {project_id}."
                    )
                )
                return

            # Output results
            self.stdout.write(f"Total Documents Retrieved: {len(tokens)}")
            self.stdout.write(f"Maximum Tokens Per Document: {max(tokens)}")

        except Exception as e:
            logger.error(f"An error occurred during analysis: {e}")
            self.stderr.write(f"Error: {e}")
