import logging

import psycopg2

from django.conf import settings
from psycopg2 import OperationalError

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DATABASE_URI = settings.DATABASE_URI


def get_data(project_id: int) -> list:
    """
    Retrieve all documents related to a specific project ID from the database.

    Parameters
    ----------
    project_id : int
        The project ID for which to query documents.

    Returns
    -------
    list
        A list of tuples containing the document data.

    Raises
    ------
    OperationalError
        If a database connection error occurs.
    Exception
        For other issues that may arise when executing the query.
    """
    try:
        conn = psycopg2.connect(DATABASE_URI)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id, raw_document_id, preprocessed_document FROM public.literev_document WHERE project_id={project_id};"
        )
        data = cursor.fetchall()
        conn.close()
        logging.info(f"Retrieved {len(data)} records for project {project_id}")
        return data
    except OperationalError as e:
        logging.error(f"Database connection failed: {e}")
        raise
    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        raise


if __name__ == "__main__":
    try:
        # The variable project_id will replace with the actual project ID
        project_id = 1
        project_data = get_data(project_id)
        logging.info(project_data[:1])  # Log first record for verification
    except Exception as e:
        logging.error(f"Error retrieving data: {e}")
