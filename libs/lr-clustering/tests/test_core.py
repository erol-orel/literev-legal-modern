from __future__ import annotations

from lr_clustering import create_tfidf_matrix


def test_create_tfidf_matrix_returns_expected_shape() -> None:
    matrix, columns = create_tfidf_matrix(
        [
            "contrat bail",
            "bail locataire",
        ]
    )

    assert matrix.shape == (2, 3)
    assert set(columns) == {"bail", "contrat", "locataire"}
