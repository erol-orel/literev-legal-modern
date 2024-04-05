from __future__ import annotations

import hdbscan
import numpy as np
import numpy.typing as npt
import pandas as pd

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
    print("tf idf created")
    embedding_2d_array = pacmap_default(tf_idf)
    print("embedding done")
    # run optimization
    n_trials = 20
    study = optimization(
        project,
        tf_idf,
        "study_project_" + str(project.id),
        n_trials,  # default 100
    )

    print("Optimization end", project.id)
    # extract best study
    best_study_clusterer = retrieve_best_study(project, tf_idf, study)

    return embedding_2d_array, best_study_clusterer, tf_idf_sorted
