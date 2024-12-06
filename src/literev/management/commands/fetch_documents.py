import logging

import joblib
import optuna
import psycopg2

from django.conf import settings
from django.core.management.base import BaseCommand
from psycopg2 import OperationalError

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DATABASE_URI = settings.DATABASE_URI
PKL_DATA = settings.PKL_DATA


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


class Command(BaseCommand):
    help = "Check access to DB and check permissions for writing in volume"

    def handle(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.info("Checking access to db ...")

        try:
            # The variable project_id will replace with the actual project ID
            project_id = 1
            project_data = get_data(project_id)
            logging.info(project_data[:1])  # Log first record for verification

            name = (
                "study_" + "project_new" + str(project_id)
            )  # f"literev_study_{number}"

            study_names = optuna.study.get_all_study_names(
                storage=DATABASE_URI
            )
            logging.info(study_names)
            logging.info(f"actual study: {name}")
            if name in study_names:
                logging.info("Access to db granted")
            else:
                logging.info(f"There is no study with name: {name}")

            try:
                value_test = 634.00023

                joblib.dump(
                    value_test,
                    PKL_DATA / f"value_test_{project_id}.pkl",
                )
                logging.info(f"Writting permissions granted in {PKL_DATA}")

            except Exception as e:
                logging.info(f"Error writing in {PKL_DATA}")
                logging.info(e)

        except Exception as e:
            logging.error(f"An error occurred: {e}")
