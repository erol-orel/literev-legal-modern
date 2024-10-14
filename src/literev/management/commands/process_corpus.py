# process_corpus.py
import datetime
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from literev.libs.collectors import ElasticSearchCollector
from literev.models import Project
from literev.tasks import launch_process

# Configure logging for this script
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

User = get_user_model()


def count_all_corpus(index_name: str) -> int:
    """
    Count all documents in the Elasticsearch corpus for a given index.

    Parameters
    ----------
    index_name : str
        The name of the Elasticsearch index.

    Returns
    -------
    int
        The total number of documents in the specified index.
    """
    es_collector = ElasticSearchCollector(index_name=index_name)
    try:
        total_documents = es_collector.count_all_corpus()
        logger.info(
            f"Total documents for index {index_name}: {total_documents}"
        )
        return total_documents

    except Exception as e:
        logger.error(
            f"Failed to count documents for index {index_name}. Error: {e}"
        )
        return 0


def process_all_documents(
    index_name: str,
    user: User,
    start_date: datetime.date,
    end_date: datetime.date,
) -> None:
    """
    Create a project for processing all documents from the specified Elasticsearch index.

    Parameters
    ----------
    index_name : str
        The name of the Elasticsearch index.
    user : User
        The Django user object associated with the project.
    start_date : datetime.date
        The start date for filtering documents.
    end_date : datetime.date
        The end date for filtering documents.
    """
    total_documents = count_all_corpus(index_name=index_name)
    try:
        # Create a new project specifically for processing the entire corpus
        project = Project.objects.create(
            user=user,
            name=f"Process All Documents ({index_name})",
            creation_date=datetime.datetime.now(),
            query="#PROCESS-ALL-CORPUS-LITEREV-00",
            total_documents=total_documents,
            selected_indices=[index_name],
            range_begin_date=start_date,
            range_end_date=end_date,
            is_running=False,
            is_finish=False,
        )
        logger.info(
            f"Project created with ID: {project.id} for user: {user.username}"
        )

    except Exception as e:
        logger.warning(
            f"Failed to create project for index '{index_name}'. Error: {e}"
        )
        return

    try:
        if launch_process(project):
            logger.info(
                f"Successfully started processing the corpus for project ID: {project.id}"
            )
        else:
            logger.warning(
                f"Failed to launch process for project ID: {project.id}"
            )
    except Exception as e:
        logger.warning(
            f"Error while launching process for project ID: {project.id}. Error: {e}"
        )
        project.delete()
        logger.warning(f"Deleted project ID: {project.id} due to failure.")


class Command(BaseCommand):
    help = "Manually initiate the processing of all documents for a given index and date range."

    def add_arguments(self, parser):
        parser.add_argument(
            "--index-name",
            "-i",
            type=str,
            required=True,
            help="The name of the Elasticsearch index to process all documents from.",
        )
        parser.add_argument(
            "--username",
            "-u",
            type=str,
            required=True,
            help="Username of the user initiating the process.",
        )
        parser.add_argument(
            "--start-date",
            "-s",
            type=str,
            default="2000-01-01",
            help="The starting date for filtering documents in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--end-date",
            "-e",
            type=str,
            default=str(datetime.date.today()),
            help="The ending date for filtering documents in YYYY-MM-DD format.",
        )

    def handle(self, *args, **options):
        index_name = options["index_name"]
        username = options["username"]
        start_date_str = options["start_date"]
        end_date_str = options["end_date"]

        try:
            start_date = datetime.datetime.strptime(
                start_date_str, "%Y-%m-%d"
            ).date()
        except ValueError:
            self.stderr.write(
                self.style.ERROR(
                    f"Invalid start date format: {start_date_str}"
                )
            )
            return

        try:
            end_date = datetime.datetime.strptime(
                end_date_str, "%Y-%m-%d"
            ).date()
        except ValueError:
            self.stderr.write(
                self.style.ERROR(f"Invalid end date format: {end_date_str}")
            )
            return

        user = User.objects.filter(username=username).first()
        if not user:
            self.stderr.write(
                self.style.ERROR(f"User '{username}' not found.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Processing index: {index_name} for user: {username} from {start_date} to {end_date}"
            )
        )

        process_all_documents(
            index_name=index_name,
            user=user,
            start_date=start_date,
            end_date=end_date,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed all corpus for index: {index_name} for user: {username}."
            )
        )
