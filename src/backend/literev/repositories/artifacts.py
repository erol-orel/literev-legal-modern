from __future__ import annotations

import joblib

from django.conf import settings


def save_es_scores(project_id: int, scores: dict[int, float]) -> None:
    joblib.dump(
        scores, settings.ARTICLE_DATA / f"es_scores_project_{project_id}.pkl"
    )


def load_es_scores(project_id: int) -> dict[int, float]:
    path = settings.ARTICLE_DATA / f"es_scores_project_{project_id}.pkl"
    if not path.exists():
        return {}
    return joblib.load(path)
