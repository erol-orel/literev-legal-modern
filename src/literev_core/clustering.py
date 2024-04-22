from __future__ import annotations

import logging

import hdbscan
import numpy as np
import numpy.typing as npt
import pandas as pd

from django.conf import settings

from literev.models import Project

from .cluster_utils import (
    create_tfidf_matrix,
    optimization,
    pacmap_default,
    retrieve_best_study,
)


def cluster(
    project: Project, corpuses: list[str]
) -> tuple[npt.NDArray[np.float_], hdbscan.HDBSCAN, pd.DataFrame]:
    tf_idf, tf_idf_sorted = create_tfidf_matrix(corpuses)
    logging.info("tf idf created")
    embedding_2d_array = pacmap_default(tf_idf)
    logging.info("embedding done")
    # run optimization

    n_trials = settings.NUMBER_TRIALS
    study = optimization(
        project,
        tf_idf,
        "study_project_" + str(project.id),
        n_trials,  # default 100
    )

    logging.info("Optimization end", project.id)
    # extract best study
    best_study_clusterer = retrieve_best_study(project, tf_idf, study)

    return embedding_2d_array, best_study_clusterer, tf_idf_sorted
