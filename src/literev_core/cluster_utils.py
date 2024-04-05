import logging

from typing import Optional, cast

import hdbscan
import numpy as np
import numpy.typing as npt
import optuna
import pacmap
import pandas as pd
import scipy

from scipy.sparse import csr_matrix
from sklearn import metrics  # Unused cluster
from sklearn.feature_extraction.text import TfidfVectorizer

from literev.models import Project

set_seed = 5


class PacMapHDBScan:
    matrix: csr_matrix
    pacmap_n_components: int
    pacmap_n_neighbors: Optional[int]
    pacmap_MN_ratio: float
    pacmap_FP_ratio: float
    pacmap_init: str
    pacmap_distance: str
    hdbscan_min_cluster_size: int
    hdbscan_min_samples: Optional[int]
    hdbscan_cluster_selection_method: str
    hdbscan_metric: str
    embedding: hdbscan.HDBSCAN
    clusterer: hdbscan.HDBSCAN
    score: float
    coherence: float
    col_len: int
    n_noise: int
    perc_noise: float

    def __init__(
        self,
        tf_idf: csr_matrix,
        pacmap_n_components: int = 2,
        pacmap_n_neighbors: Optional[int] = None,
        pacmap_MN_ratio: float = 0.5,
        pacmap_FP_ratio: float = 2.0,
        pacmap_init: str = "random",
        pacmap_distance: str = "angular",
        hdbscan_min_cluster_size: int = 5,
        hdbscan_min_samples: Optional[int] = None,
        hdbscan_cluster_selection_method: str = "leaf",
        hdbscan_metric: str = "cosine",
    ) -> None:
        self.matrix = tf_idf

        self.pacmap_n_components = pacmap_n_components
        self.pacmap_n_neighbors = pacmap_n_neighbors
        self.pacmap_MN_ratio = pacmap_MN_ratio
        self.pacmap_FP_ratio = pacmap_FP_ratio
        self.pacmap_init = pacmap_init
        self.pacmap_distance = pacmap_distance

        self.hdbscan_min_cluster_size = hdbscan_min_cluster_size
        self.hdbscan_min_samples = hdbscan_min_samples
        self.hdbscan_cluster_selection_method = (
            hdbscan_cluster_selection_method
        )
        self.hdbscan_metric = hdbscan_metric

    def evaluate(self) -> float:
        self._project_with_pacmap_and_cluster()
        self._compute_coherence_value()
        self._print_results()
        return self.score  # , self.coherence

    def _project_with_pacmap_and_cluster(self) -> None:
        np.random.seed(set_seed)  # WORKAROUND check seed for randomness

        self.embedding = pacmap.PaCMAP(
            random_state=set_seed,  # WORKAROUND check seed for randomness
            n_components=self.pacmap_n_components,
            n_neighbors=self.pacmap_n_neighbors,
            MN_ratio=self.pacmap_MN_ratio,
            FP_ratio=self.pacmap_FP_ratio,
            distance=self.pacmap_distance,
            apply_pca=False,
        ).fit_transform(self.matrix.toarray(), init=self.pacmap_init)

        self.clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.hdbscan_min_cluster_size,
            min_samples=self.hdbscan_min_samples,
            metric=self.hdbscan_metric,
            gen_min_span_tree=True,
            algorithm="generic",
            cluster_selection_method=self.hdbscan_cluster_selection_method,
            approx_min_span_tree=False,
            allow_single_cluster=True,
            prediction_data=False,
        ).fit(csr_matrix(self.embedding, dtype=np.float64))

        self.col_len = len(set(self.clusterer.labels_)) - (
            1 if -1 in self.clusterer.labels_ else 0
        )
        self.n_noise = list(self.clusterer.labels_).count(-1)
        self.perc_noise = (self.n_noise / self.matrix.shape[0]) * 100

    def _compute_coherence_value(self) -> None:
        try:
            self.coherence = metrics.silhouette_score(
                self.embedding,
                self.clusterer.labels_,
                metric="cosine",
            )
        except ValueError as e:
            print(e)
            self.coherence = -1

        self.score = self.clusterer.relative_validity_

    def _print_results(self) -> None:
        logging.info("Number of clusters: %d" % self.col_len)
        logging.info("Number of noise points: %d" % self.n_noise)
        logging.info("Percentage of noise points: %0.1f" % self.perc_noise)
        logging.info("Silhouette Coefficient: %0.3f" % self.coherence)
        logging.info("DBCV Score: %0.3f" % self.score)


class Objective:
    tf_idf: csr_matrix
    project: Project

    def __init__(self, tf_idf: csr_matrix, project: Project) -> None:
        self.tf_idf = tf_idf
        self.project = project

    def __call__(self, trial: optuna.trial.Trial) -> float:
        tf_idf = self.tf_idf
        pacmap_n_components = trial.suggest_int(
            "pacmap_n_components",
            2,
            min(min(tf_idf.shape[0], tf_idf.shape[1]), 400),
        )
        pacmap_FP_ratio = trial.suggest_float(
            "pacmap_FP_ratio", 2, max(min(round(tf_idf.shape[0] / 20), 20), 3)
        )

        hdbscan_min_cluster_size = trial.suggest_int(
            "hdbscan_min_cluster_size", 2, round(tf_idf.shape[0] / 2) - 1
        )
        hdbscan_min_samples = trial.suggest_int(
            "hdbscan_min_samples", 2, round(tf_idf.shape[0] / 2) - 1
        )

        study = PacMapHDBScan(
            tf_idf,
            pacmap_n_components=pacmap_n_components,
            pacmap_FP_ratio=pacmap_FP_ratio,
            hdbscan_min_cluster_size=hdbscan_min_cluster_size,
            hdbscan_min_samples=hdbscan_min_samples,
        )

        return_data = study.evaluate()

        # TODO: Check number of trials
        # increment the number of finish trial
        # with transaction.atomic():
        #     number_of_trials, _ = NumberTrial.objects.get_or_create(
        #         research=self.research
        #     )
        #     number_of_trials.counter = F("counter") + 1
        #     number_of_trials.save()

        # write the score if it is greater

        # TODO: Check this part of db to store best_dbcv
        current_score = self.project.best_dbcv
        new_score = study.score
        if new_score > current_score:
            self.project.best_dbcv = new_score
            self.project.save()

        return return_data


def retrieve_best_study(
    project: Project, tf_idf: csr_matrix, study: optuna.study.Study
) -> hdbscan.HDBSCAN:
    best_study = PacMapHDBScan(
        tf_idf,
        pacmap_n_components=study.best_trials[0].params["pacmap_n_components"],
        pacmap_FP_ratio=study.best_trials[0].params["pacmap_FP_ratio"],
        hdbscan_min_cluster_size=study.best_trials[0].params[
            "hdbscan_min_cluster_size"
        ],
        hdbscan_min_samples=study.best_trials[0].params["hdbscan_min_samples"],
    )

    best_study.evaluate()

    # note: type is None and I am afraid that it will be a problem. Hence the
    #       exact formulation with the log10
    #       research.number_neighbour = best_study.pacmap_n_neighbors

    # TODO: Check the purpose of project.number_neighbour
    # if tf_idf.shape[0] <= 10000:
    #     project.number_neighbour = 10
    # else:
    #     project.number_neighbour = int(
    #         round(10 + 15 * (np.log10(tf_idf.shape[0]) - 4))
    #     )

    project.best_dbcv = best_study.score
    project.save()
    best_study_clusterer = best_study.clusterer

    return best_study_clusterer


def optimization(
    project: Project,
    tf_idf: csr_matrix,
    name: str,
    n_trials: int = 100,
) -> optuna.study.Study:
    # db = settings.DATABASES["default"]

    # if "postgres" in db["ENGINE"]:
    #     storage = (
    #         f"postgresql://{db['USER']}:{db['PASSWORD']}@"
    #         f"{db['HOST']}:{db['PORT']}/{db['NAME']}"
    #     )
    # elif "sqlite" in db["ENGINE"]:
    #     storage = db["NAME"]
    # else:
    #     raise Exception(f"Database source {db['ENGINE']} not recognized.")

    try:
        objective = Objective(tf_idf, project)
    except Exception as e:
        print(e)
        print("objective error")
        raise (Exception)

    try:
        study = optuna.create_study(
            study_name=name,
            # storage=storage,
            direction="maximize",
            load_if_exists=True,
        )
    except Exception as e:
        print("error in create study")
        print(e)
        raise (Exception)

    try:
        study.optimize(
            objective,
            n_trials=n_trials,
            gc_after_trial=True,
            n_jobs=4,  # note: disabled? for now,
            catch=(AttributeError, ValueError),
            # callbacks=[close_connections_on_done], TODO: add later
        )
    except:
        print("error in optimize study")
        raise (Exception)

    return study


def pacmap_default(tf_idf: csr_matrix) -> npt.NDArray[np.float_]:
    np.random.seed(set_seed)

    # For random seed check if is needed to set for numpy as well
    # documentation https://pypi.org/project/pacmap/
    # Setting the random_state will affect the numpy random seed
    # in your local environment. However, you may still get
    # different results even if the random_state parameter
    # is set to be the same. This is because numba
    # parallelization makes some of the functions
    # undeterministic. That being said, fixing the
    # random state will always give you the same set
    # of pairs and initialization, which ensure the difference is minimal.

    # https://github.com/YingfanWang/PaCMAP/issues/7#issuecomment-838863998
    # if not tf_idf.shape[0] > 10:
    #     # note: not enough data, using PCA instead
    #     embedding_2d_pca = PCA(
    #         n_components=2, copy="FALSE", random_state=set_seed
    #     )
    #     return cast(
    #         npt.NDArray[np.float_],
    #         embedding_2d_pca.fit_transform(tf_idf.toarray()),
    #     )

    embedding_2d_pacmap = pacmap.PaCMAP(
        n_components=2,
        n_neighbors=None,
        MN_ratio=0.5,
        FP_ratio=2.0,
        random_state=set_seed,
        distance="angular",
        apply_pca=False,
        verbose=False,
    )

    return cast(
        npt.NDArray[np.float_],
        embedding_2d_pacmap.fit_transform(tf_idf.toarray(), init="random"),
    )


def create_tfidf_matrix(
    corpuses: list[str],
) -> tuple[scipy.sparse.csr_matrix, pd.DataFrame]:
    try:
        tfidfVectorizer = TfidfVectorizer()
    except Exception as e:
        print("error tfidfvectorizer")
        print(e)
    try:
        tf_idf = tfidfVectorizer.fit_transform(corpuses)
    except Exception as e:
        print("error tfidfvectorizer fitting")
        print(e)

    tf_idf_sorted = (
        pd.DataFrame(
            tf_idf.toarray(), columns=tfidfVectorizer.get_feature_names_out()
        )
        .transpose()
        .iloc[
            list(
                np.argsort(
                    np.array(tf_idf.transpose().sum(axis=1)).reshape(-1)
                )
            )
        ]
    )

    return tf_idf, tf_idf_sorted
