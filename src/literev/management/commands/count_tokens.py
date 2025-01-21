import logging

import pandas as pd
import psycopg2
import tiktoken

from django.conf import settings
from django.core.management.base import BaseCommand
from psycopg2 import OperationalError

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DATABASE_URI = settings.DATABASE_URI
PKL_DATA = settings.PKL_DATA

GPT_MODEL = "gpt-4o-mini"

enc = tiktoken.encoding_for_model(GPT_MODEL)


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
            f"SELECT id, raw_document_id, raw_document_text FROM public.literev_document WHERE project_id={project_id};"
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


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


class Command(BaseCommand):
    help = "Count token from documents given project"

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.info("Checking access to db ...")

        try:
            # The variable project_id will replace with the actual project ID
            project_id = 1
            project_data = get_data(project_id)
            # logging.info(project_data[:1])  # Logs first record for verification
            # print("all documents")
            # print(len(project_data))

            data_dict = {}
            data_dict["id"] = []
            data_dict["raw_id"] = []
            data_dict["number_words"] = []
            data_dict["tokens"] = []

            for document in project_data:
                if document[2] == None or document[2] == "":
                    continue
                data_dict["id"].append(document[0])
                data_dict["raw_id"].append(document[1])
                data_dict["number_words"].append(len(document[2].split()))
                data_dict["tokens"].append(count_tokens(document[2]))

            print("Max tokens in a document: ", max(data_dict["tokens"]))
            print(
                "Average words per document: ",
                sum(data_dict["number_words"])
                // len(data_dict["number_words"]),
            )
            print(
                "Average tokens per document: ",
                sum(data_dict["tokens"]) // len(data_dict["tokens"]),
            )
            print("Min tokens in a document: ", min(data_dict["tokens"]))

            with open(f"statistical_data_project_{project_id}.txt", "w") as f:
                f.write(
                    "average number words: "
                    + str(
                        sum(data_dict["number_words"])
                        // len(data_dict["number_words"])
                    )
                )
                f.write("\n")
                f.write("max number tokens: " + str(max(data_dict["tokens"])))
                f.write("\n")
                f.write("min number tokens" + str(min(data_dict["tokens"])))
                f.write("\n")
                f.write(
                    "avg number tokens: "
                    + str(sum(data_dict["tokens"]) // len(data_dict["tokens"]))
                )
                f.write("\n")

            df = pd.DataFrame.from_dict(data_dict)
            df.to_csv(f"tokens_detailed_project_{project_id}.csv", index=False)

        except Exception as e:
            logging.error(f"An error occurred: {e}")
