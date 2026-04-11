# process_corpus.py
import datetime
import logging

from django.core.management.base import BaseCommand

from literev.libs.collectors import ElasticSearchCollector
from literev.models import Project, User
from literev.tasks import launch_process

# Configure logging for this script
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def process_all_documents(
    index_name: str,
    search_term: str,
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

    es_collector = ElasticSearchCollector(index_name=index_name)

    try:
        total_documents = es_collector.count_all_documents()
        project = create_project(
            index_name,
            search_term,
            user,
            total_documents,
            start_date,
            end_date,
        )
        logger.info(
            f"Project created with ID: {project.id} for user: {user.username}"
        )

        if launch_process(project):
            logger.info(
                f"Successfully started processing for project ID: {project.id}"
            )
        else:
            handle_project_failure(project, "Failed to launch process.")

    except Exception as e:
        logger.error(
            f"Error during processing for index '{index_name}'. Error: {e}"
        )


def create_project(
    index_name: str,
    search_term: str,
    user: User,
    total_documents: int,
    start_date: datetime.date,
    end_date: datetime.date,
) -> Project:
    """
    Create a new Project instance for document processing.

    Parameters
    ----------
    user : User
        The Django user object associated with the project.
    index_name : str
        The name of the Elasticsearch index.
    total_documents : int
        The total number of documents in the index.
    start_date : datetime.date
        The start date for filtering documents.
    end_date : datetime.date
        The end date for filtering documents.

    Returns
    -------
    Project
        The created project object.
    """
    return Project.objects.create(
        user=user,
        name=f"Process All Documents ({index_name})",
        creation_date=datetime.datetime.now(),
        query=search_term,
        total_documents=total_documents,
        selected_indices=[index_name],
        range_begin_date=start_date,
        range_end_date=end_date,
        is_running=False,
        is_finish=False,
    )


def handle_project_failure(project: Project, message: str) -> None:
    """
    Handle project failure by logging an error and deleting the project.

    Parameters
    ----------
    project : Project
        The project object that failed.
    message : str
        A custom error message to log.
    """
    logger.warning(f"{message} Project ID: {project.id}")
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
            "--search-term",
            "-q",
            type=str,
            required=True,
            help="The query .",
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

    def handle(self, **options):  # removed ` *args,` because linter
        index_name = options["index_name"]
        search_term = options["search_term"]
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
            search_term=search_term,
            user=user,
            start_date=start_date,
            end_date=end_date,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed all corpus for index: {index_name} for user: {username}."
            )
        )
