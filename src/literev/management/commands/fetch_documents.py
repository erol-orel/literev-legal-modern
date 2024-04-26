import logging
import os

import psycopg2

from psycopg2 import OperationalError

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Retrieve database connection info from environment variables
POSTGRES_DB = os.getenv("POSTGRES_DB", "literev")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "192.168.16.2")
POSTGRES_USER = os.getenv("POSTGRES_USER", "literev")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "literevqsx3409po")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "35432")


def generate_database_uri():
    """Generates a database storage URL for Optuna."""
    return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


def get_data(project_id: int) -> list:
    """
    Retrieve all documents related to a specific project ID from the database.

    Parameters
    ----------
    project_id : int
        The project ID to query documents for.

    Returns
    -------
    list
        A list of tuples containing the document data.

    Raises
    ------
    Exception
        Raises an exception if database connection or queries fail.
    """
    try:
        conn = psycopg2.connect(
            database=POSTGRES_DB,
            host=POSTGRES_HOST,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            port=POSTGRES_PORT,
        )
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id, raw_document_id, preprocessed_document FROM public.literev_document WHERE project_id={project_id};"
        )
        data = cursor.fetchall()
        # Use only for testing
        # data = cursor.fetchmany(size=2000)
        conn.close()
        logging.info(f"Retrieved {len(data)} records for project {project_id}")
        return data
    except OperationalError as e:
        logging.error(f"Database connection failed: {e}")
        raise
    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        raise


# Example usage:
if __name__ == "__main__":
    try:
        project_data = get_data(1)  # Adjust the project_id as needed
        logging.info(project_data[:1])  # Log first record for verification
    except Exception as e:
        logging.error(f"Error retrieving data: {e}")
