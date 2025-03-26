import datetime

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Project(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, default=None
    )
    name = models.CharField(max_length=256, default="No name")
    creation_date = models.DateField(default=datetime.date(1900, 1, 1))
    query = models.CharField(max_length=4096)
    natural_language_query = models.CharField(
        max_length=4096, default="", blank=True, null=True
    )
    range_begin_date = models.DateField(default=datetime.date(1900, 1, 1))
    range_end_date = models.DateField(default=datetime.date(1900, 1, 1))
    total_documents = models.IntegerField(default=0)
    selected_indices = models.JSONField(default=list)
    step = models.CharField(max_length=256, default="getting_documents")
    step_number = models.IntegerField(default=0)
    is_finish = models.BooleanField(default=False)
    is_running = models.BooleanField(default=False)
    best_dbcv = models.FloatField(default=0.0)
    actual_task_code = models.CharField(max_length=256, default="", blank=True)


class Document(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    chamber = models.CharField(
        max_length=256, default="", null=True, blank=True
    )
    decision_type = models.CharField(
        max_length=256, default="", null=True, blank=True
    )
    decision_date = models.DateField(
        default=datetime.date(1900, 1, 1), null=True, blank=True
    )  # Some docs have it as a None
    procedure_type = models.CharField(max_length=256, default="")
    descriptors = models.TextField(default="", null=True, blank=True)
    standards = models.CharField(
        max_length=512, default="", null=True, blank=True
    )  # normes
    result = models.CharField(
        max_length=256, default="", null=True, blank=True
    )
    raw_document_id = models.CharField(
        max_length=256, default="", null=True, blank=True
    )
    raw_document_text = models.TextField(
        default="", null=True, blank=True
    )  # added for debugging
    prepared_for_ngrams = models.TextField(default="", null=True, blank=True)
    preprocessed_document = models.TextField(default="", null=True, blank=True)
    procedure_year = models.DateField(
        default=datetime.date(1900, 1, 1), null=True, blank=True
    )


class Cluster(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    order = models.IntegerField(default=-1)
    topic = models.CharField(max_length=8196)
    summary = models.TextField(default="")


class ClusterElement(models.Model):
    pos_x = models.FloatField()
    pos_y = models.FloatField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)


class TableChoice(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, default=None, null=True, blank=True
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    to_display = models.BooleanField(default=True)
    is_initial = models.BooleanField(default=True)
    is_check = models.BooleanField(null=True)


class ProjectRefinement(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=1024)
    origin = models.ForeignKey(
        "ProjectRefinement", on_delete=models.SET_NULL, null=True, blank=True
    )
    filters = models.JSONField(default=dict)


class RefinementIteration(models.Model):
    refinement = models.ForeignKey(ProjectRefinement, on_delete=models.CASCADE)
    parent_iteration = models.ForeignKey(
        "RefinementIteration", on_delete=models.SET_NULL, null=True, blank=True
    )
    number_documents = models.IntegerField(default=0)
    checked_documents_ids = models.JSONField(default=list)
    excluded_documents_ids = models.JSONField(default=list)
    new_neighbors_ids = models.JSONField(default=list)
    result_documents_ids = models.JSONField(default=list)


class ProjectRAG(models.Model):
    """
    Model representing a RAG (Retrieval-Augmented Generation) record for a specific project.

    Fields:
        project (ForeignKey): Points to the related Project model.
        query (CharField): The query used for the RAG.
        created_at (DateTimeField): Timestamp of when this data was created.
        status (CharField): Indicates the current status of the RAG, either 'completed' or 'in-progress'.
    """

    STATUS_CHOICES = [
        ("completed", "Completed"),
        ("in-progress", "In Progress"),
        ("failed", "Failed"),
    ]

    project = models.ForeignKey(
        "Project", on_delete=models.CASCADE, related_name="project_rags"
    )
    query = models.CharField(max_length=500)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="in-progress"
    )
    summary_answer = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return (
            f"ProjectRAG for Project ID {self.project.id} - "
            f"Query: {self.query} - Status: {self.status}"
        )


class ProjectDocumentRAG(models.Model):
    """
    Model representing the items associated with a specific ProjectRAG entry.

    Fields:
        project_rag (ForeignKey): Points to the related ProjectRAG.
        document (ForeignKey): Points to the related Document.
        citation (TextField): A sentence or paragraph as a citation.
        answer (TextField): The answer generated from the RAG.
        from_full_text (BooleanField): Indicates if the answer was generated from the PDF.
    """

    project_rag = models.ForeignKey(
        ProjectRAG, on_delete=models.CASCADE, related_name="documents"
    )
    document = models.ForeignKey(
        "Document", on_delete=models.CASCADE, related_name="document_rags"
    )
    citation = models.TextField()
    answer = models.TextField()

    def set_source(self, source: str) -> None:
        """
        Set the source type for the answer (pdf or abstract).

        Parameters
        ----------
        source : str
            The content source ('pdf' or 'abstract') used to generate the answer.
        """
        self.from_full_text = source == "pdf"
        self.save()

    def __str__(self) -> str:
        return (
            f"ProjectDocumentRAG for ProjectRAG ID {self.project_rag.id} - "
            f"Document ID {self.document.id}"
        )


class ProjectRAGStats(models.Model):
    """
    Stores classification statistics for closed-ended ProjectRAG questions.

    Linked to ProjectRAG via OneToOneField.
    """

    project_rag = models.OneToOneField(
        ProjectRAG, on_delete=models.CASCADE, related_name="stats"
    )

    classification_stats = models.JSONField(default=dict)

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, default=None
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Stats for ProjectRAG ID {self.project_rag.id}"
