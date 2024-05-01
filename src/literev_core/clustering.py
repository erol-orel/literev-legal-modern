from __future__ import annotations

import logging

import hdbscan
import joblib
import numpy as np
import numpy.typing as npt
import optuna
import pandas as pd

from django.conf import settings
from joblib import Parallel, delayed

from literev.models import Project

from .cluster_utils import (
    Objective,
    create_tfidf_matrix,
    pacmap_default,
    retrieve_best_study,
)


def optimize(objective, n_trials, storage, name):
    study = optuna.load_study(study_name=name, storage=storage)
    study.optimize(
        objective,
        gc_after_trial=True,
        catch=(AttributeError, ValueError),
        n_trials=n_trials,
    )


def cluster(
    project: Project, corpuses: list[str]
) -> tuple[npt.NDArray[np.float_], hdbscan.HDBSCAN, pd.DataFrame]:
    PKL_PATH = settings.PKL_DATA
    db = settings.DATABASES["default"]
    if "postgres" in db["ENGINE"]:
        storage = (
            f"postgresql://{db['USER']}:{db['PASSWORD']}@"
            f"{db['HOST']}:{db['PORT']}/{db['NAME']}"
        )
    else:
        raise Exception(f"Unsupported database engine: {db['ENGINE']}")

    try:
        best_study_clusterer = joblib.load(
            PKL_PATH / f"best_study_{project.pk}.pkl"
        )

        best_score = joblib.load(PKL_PATH / f"best_score_{project.pk}.pkl")
        project.best_dbcv = best_score
        project.save()

        logging.info("pkl files opened")

        tf_idf, tf_idf_sorted = create_tfidf_matrix(corpuses)
        # To use when best_study is not saved extract directly from DB
        # name = f"study_{project.id}"
        # study = optuna.load_study(study_name=name, storage=storage)
        # best_study_clusterer = retrieve_best_study(project, tf_idf, study)

        embedding_2d_array = pacmap_default(tf_idf)

        logging.info("getting best from saved data")

    except:
        tf_idf, tf_idf_sorted = create_tfidf_matrix(corpuses)
        logging.info("tf idf created")
        embedding_2d_array = pacmap_default(tf_idf)
        logging.info("embedding done")

        try:
            objective = Objective(tf_idf, project)  # , project)
        except Exception as e:
            logging.warning(e)
            logging.warning("objective error")
            raise (Exception)

        # run optimization
        study = optuna.create_study(
            study_name=f"study_{project.id}",
            storage=storage,
            direction="maximize",
            load_if_exists=True,
        )

        # in this way we send chunk of 10s to the optimize function
        n_trials = settings.NUMBER_TRIALS // 10  # 100/10 = 10

        with joblib.parallel_backend("threading", n_jobs=4):
            Parallel()(
                [
                    delayed(optimize)(
                        objective,
                        n_trials=n_trials,
                        storage=storage,
                        name=f"study_{project.id}",
                    )
                    for _ in range(10)
                ]
            )
        # uncomment this code if you want to run with one core
        # optimize(objective, n_trials, storage, f"study_{project.id}")

        logging.info(f"Number of finished trials: {len(study.trials)}")

        logging.info(f"Optimization end {project.pk}")
        # extract best study
        best_study_clusterer = retrieve_best_study(project, tf_idf, study)

    return embedding_2d_array, best_study_clusterer, tf_idf_sorted
