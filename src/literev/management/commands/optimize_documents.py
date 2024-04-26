import logging
import os

import joblib
import optuna

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from joblib import Parallel, delayed

from .document_cluster_optimization import (
    _create_tfidf_matrix,
    _Objective,
    _retrieve_best_study,
)
from .fetch_documents import get_data

DATABASE_URI = settings.DATABASE_URI
PKL_DATA = settings.PKL_DATA


class Command(BaseCommand):
    help = "Optimizes document clustering using advanced text analysis techniques."

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.info("Starting the document optimization process...")

        try:
            number = 1

            os.makedirs(PKL_DATA, exist_ok=True)

            storage = DATABASE_URI

            data = get_data(number)

            corpuses = [corpus for _, __, corpus in data]

            tf_idf = _create_tfidf_matrix(corpuses)

            name = "study_" + str(number)  # f"literev_study_{number}"

            objective = _Objective(tf_idf)

            study = optuna.create_study(
                study_name=name,  # TODO: Check this name
                storage=storage,
                direction="maximize",
                load_if_exists=True,
            )

            # It's important to manage threading if objects cannot be easily serialized
            with joblib.parallel_backend("threading", n_jobs=5):
                Parallel()(
                    [
                        delayed(self.optimize_study)(
                            objective, n_trials=30, storage=storage, name=name
                        )
                        for _ in range(10)
                    ]
                )

            study = optuna.load_study(study_name=name, storage=storage)

            best_study_clusterer = _retrieve_best_study(
                tf_idf, study
            )  # Ensure both tf_idf and study are passed

            joblib.dump(
                best_study_clusterer,
                PKL_DATA / f"best_study_{number}.pkl",
            )

            logging.info(
                "Document optimization process completed successfully."
            )
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            raise CommandError(f"Error during document optimization: {e}")

    def optimize_study(self, objective, n_trials, storage, name):
        study = optuna.load_study(study_name=name, storage=storage)
        study.optimize(
            objective,
            n_trials=n_trials,
            catch=(AttributeError, ValueError),
            gc_after_trial=True,
        )
