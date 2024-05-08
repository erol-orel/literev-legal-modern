from __future__ import annotations

import logging

import hdbscan
import joblib
import numpy as np
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

logger = logging.getLogger(__name__)

DATABASE_URI = settings.DATABASE_URI


def optimize(
    objective: Objective, n_trials: int, storage: str, name: str
) -> None:
    """
    Execute the optimization process for a given study.

    Parameters
    ----------
    objective : Objective
        The objective function to optimize.
    n_trials : int
        The number of trials to perform.
    storage : str
        The storage URL for Optuna.
    name : str
        The name of the Optuna study.
    """
    try:
        study = optuna.load_study(study_name=name, storage=storage)
        study.optimize(
            objective,
            gc_after_trial=True,
            catch=(AttributeError, ValueError),
            n_trials=n_trials,
            callbacks=[optuna_logging_callback],  # Adding a logging callback
        )
    except Exception as e:
        logger.error(f"Optimization failed for {name}: {e}")
        raise


def optuna_logging_callback(
    study: optuna.study.Study, trial: optuna.trial.FrozenTrial
) -> None:
    """
    Logging callback for Optuna study optimization.

    Parameters
    ----------
    study : optuna.study.Study
        The study to which the trial belongs.
    trial : optuna.trial.FrozenTrial
        The trial that just completed or failed.
    """
    if trial.state == optuna.trial.TrialState.COMPLETE:
        logger.info(f"Trial completed: {trial.number}")
    else:
        logger.warning(f"Trial {trial.number} failed: {trial.state}")


def cluster(
    project: Project, corpuses: list[str]
) -> tuple[np.ndarray, hdbscan.HDBSCAN, pd.DataFrame]:
    """
    Perform clustering on text data using TF-IDF and PaCMAP followed by HDBSCAN.

    Parameters
    ----------
    project : Project
        The project instance containing details about the project.
    corpuses : list[str]
        List of document texts to be clustered.

    Returns
    -------
    tuple[np.ndarray, hdbscan.HDBSCAN, pd.DataFrame]
        A tuple containing the embedding array, the HDBSCAN clusterer, and the sorted TF-IDF DataFrame.
    """
    storage = DATABASE_URI
    tf_idf, tf_idf_sorted = create_tfidf_matrix(corpuses)
    embedding_2d_array = pacmap_default(tf_idf)

    objective = Objective(tf_idf, project)
    study = optuna.create_study(
        study_name=f"study_{project.id}",
        storage=storage,
        direction="maximize",
        load_if_exists=True,
    )

    try:
        n_trials = settings.NUMBER_TRIALS // 10
        n_jobs = settings.NUMBER_OPTUNA_JOBS
        with joblib.parallel_backend("threading", n_jobs=n_jobs):
            Parallel()(
                [
                    delayed(optimize)(
                        objective, n_trials, storage, f"study_{project.id}"
                    )
                    for _ in range(10)
                ]
            )
    except Exception as e:
        logger.error(f"Failed during optimization: {e}")
        raise

    if study.trials_dataframe().empty:
        logger.error("No trials were completed successfully.")
        raise ValueError("Optimization failed: No trials completed.")

    best_study_clusterer = retrieve_best_study(project, tf_idf, study)
    return embedding_2d_array, best_study_clusterer, tf_idf_sorted
