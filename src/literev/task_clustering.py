import logging

import joblib
import numpy as np
import optuna
import pandas as pd

from django.conf import settings
from django.db.models import Count

from config.celery import app
from literev.libs.nlp import nlp_topic_description
from literev.libs.utils import (
    get_database_uri,
    get_study_name,
    update_task_code,
)
from literev.models import Cluster, ClusterElement, Document, Project
from literev_core.clustering import cluster_corpuses

logger = logging.getLogger(__name__)

UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"

CLUSTERING_MIN_DOCUMENTS = settings.CLUSTERING_MIN_DOCUMENTS


@app.task(bind=True)
def back_clustering_documents(self, project_id: int):
    """
    Clusters preprocessed documents using the configured clustering algorithm.

    Parameters
    ----------
    project_id : int
        The ID of the project for which documents are clustered.
    """

    project = Project.objects.get(id=project_id)
    project.step = "clustering"
    project.save()

    update_task_code(project, self.request.id)

    documents = Document.objects.filter(project=project)

    if documents.count() < CLUSTERING_MIN_DOCUMENTS:
        return

    try:
        pp_documents = [
            document.preprocessed_document
            for document in documents
            if document.preprocessed_document != ""
        ]
        list_id_docs = [
            document.pk
            for document in documents
            if document.preprocessed_document != ""
        ]
    except Exception as e:
        logger.error("Error getting preprocessed Document from DB")
        logger.error(f"project id: {project.pk}")
        logger.error(e)
        return

    study_name = get_study_name(project)
    storage = get_database_uri()

    number_trials = settings.NUMBER_TRIALS

    try:
        study = optuna.load_study(study_name=study_name, storage=storage)
        trials = study.get_trials(deepcopy=False)

        actual_trials = len(trials)
        if actual_trials != 0:
            if actual_trials > number_trials:
                number_trials = 0
            else:
                number_trials = number_trials - actual_trials
        logging.info(f"existing trials: {actual_trials}")

    except KeyError:
        logging.info("creating a new study")

    number_jobs = settings.NUMBER_OPTUNA_JOBS

    try:
        (
            embedding_2d_array,
            best_study_clusterer,
            tf_idf,
            columns_name,
            best_score,
            number_neighbour,
        ) = cluster_corpuses(
            pp_documents, study_name, storage, number_trials, number_jobs
        )
    except Exception as e:
        logger.error(f"Error in clustering, project ID: {project.pk}")
        logger.error(e)
        return

    # update project best study values and number neighbour
    project.best_dbcv = best_score
    project.number_neighbour = number_neighbour
    project.save()

    # Removing old clusters
    Cluster.objects.filter(project=project).delete()

    num_clusters = set(best_study_clusterer.labels_)

    tf_idf_sorted = (
        pd.DataFrame(tf_idf.toarray(), columns=columns_name)
        .transpose()
        .iloc[
            list(
                np.argsort(
                    np.array(tf_idf.transpose().sum(axis=1)).reshape(-1)
                )
            )
        ]
    )

    hdbscan_scores = best_study_clusterer.probabilities_

    joblib.dump(
        hdbscan_scores,
        settings.ARTICLE_DATA / f"hdbscan_scores_project_{project.id}.pkl",
    )
    joblib.dump(
        list_id_docs,
        settings.ARTICLE_DATA / f"id_list_project_{project.id}.pkl",
    )
    joblib.dump(
        tf_idf, settings.ARTICLE_DATA / f"tf_idf_project_{project.id}.pkl"
    )
    joblib.dump(
        columns_name,
        settings.ARTICLE_DATA / f"column_name_project_{project.id}.pkl",
    )

    for cluster_num in num_clusters:
        w = np.where(best_study_clusterer.labels_ == cluster_num)[0]

        kws = (
            tf_idf_sorted.iloc[:, w]
            .mean(axis=1)
            .sort_values(ascending=False)
            .head(30)
            .index.values
        )

        labels = (
            ", ".join(kws) if cluster_num != -1 else UNCLASSIFIED_PAPERS_TOPIC
        )

        cluster = Cluster.objects.create(
            project=project,
            topic=labels,
        )

        position_article = []

        for i in range(len(best_study_clusterer.labels_)):
            if best_study_clusterer.labels_[i] == cluster_num:
                position_article.append(i)

        embedding_df = pd.DataFrame(embedding_2d_array)
        for i in position_article:
            pos_x = embedding_df[0][i]
            pos_y = embedding_df[1][i]

            document = Document.objects.filter(id=list_id_docs[i])[0]
            ClusterElement.objects.create(
                document=document,
                cluster=cluster,
                pos_x=pos_x,
                pos_y=pos_y,
            )

        # After the clustering is done, we generate the topic description
        topic_summary_text = (
            nlp_topic_description(cluster) if cluster_num != -1 else ""
        )

        cluster.summary = topic_summary_text
        cluster.save()

        # Asign order to clusters

        clusters_in_project = Cluster.objects.filter(project=project)

        if clusters_in_project:
            grouped_clusters = clusters_in_project.annotate(
                total_documents=Count("clusterelement__document"),
            ).order_by("-total_documents", "topic")

            index = 0
            for cluster in grouped_clusters:
                if cluster.topic == UNCLASSIFIED_PAPERS_TOPIC:
                    continue
                index += 1
                cluster.order = index
                cluster.save()

    # Disable sorting by keywords
    # query_keywords = extract_keywords(project.query)

    # tfidf_keywords = get_most_similar_keywords(query_keywords, columns_name)

    # joblib.dump(
    #     tfidf_keywords,
    #     settings.ARTICLE_DATA / f"tfidf_keywords_project_{project.id}.pkl",
    # )

    project.step_number = 0
    project.save()
