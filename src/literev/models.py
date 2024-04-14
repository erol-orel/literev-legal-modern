import datetime

from django.db import models

# from literev.models import CustomUser


class Project(models.Model):
    # user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=256, default="No name")
    creation_date = models.DateField(default=datetime.date(1900, 1, 1))
    query = models.CharField(max_length=4096)
    range_begin_date = models.DateField(default=datetime.date(1900, 1, 1))
    range_end_date = models.DateField(default=datetime.date(1900, 1, 1))
    total_documents = models.IntegerField(default=0)
    step = models.CharField(max_length=256, default="getting_documents")
    step_number = models.IntegerField(default=0)
    is_finish = models.BooleanField(default=False)
    is_running = models.BooleanField(default=False)
    best_dbcv = models.FloatField(default=0.0)


class Document(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    decision_type = models.CharField(
        max_length=256, default="", null=True, blank=True
    )
    decision_date = models.DateField(
        default=datetime.date(1900, 1, 1), null=True, blank=True
    )  # Some docs have it as a None
    procedure_type = models.CharField(max_length=256, default="")
    descriptors = models.TextField(default="", null=True, blank=True)
    standards = models.CharField(
        max_length=256, default="", null=True, blank=True
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
    topic = models.CharField(max_length=8196)
    summary = models.TextField(default="")


class ClusterElement(models.Model):
    pos_x = models.FloatField()
    pos_y = models.FloatField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)


# TODO: shows result in table
# class TableChoice(models.Model):
#     user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
#     research = models.ForeignKey(Research, on_delete=models.CASCADE)
#     article = models.ForeignKey(Article, on_delete=models.CASCADE)
#     to_display = models.BooleanField(default=True)
#     is_initial = models.BooleanField(default=True)
#     is_check = models.BooleanField(default=False)
