from pathlib import Path

import numpy as np
import polars as pl

from datelier.analysis.input import prepare_input
from datelier.analysis.plots import prepare_embedding_plot
from datelier.analysis.runner import run_analysis
from datelier.analysis.types import AnalysisRequest, EmbeddingResult, PCAParameters
from datelier.core import Dataset, SourceReference


def test_pca_subspace_repeatability_and_linked_plot() -> None:
    rng = np.random.default_rng(7)
    values = rng.normal(size=(60, 3)) @ np.array(
        [[5.0, 1.0, 0.0], [0.0, 2.0, 0.1], [0.0, 0.0, 0.01]]
    )
    dataset = Dataset.from_source(
        pl.DataFrame(values, schema=["x", "y", "z"]),
        SourceReference(Path("unused"), 0, 0),
    )
    prepared = prepare_input(dataset, AnalysisRequest(("x", "y", "z")))
    first, second = run_analysis(prepared), run_analysis(prepared)
    assert isinstance(first, EmbeddingResult) and isinstance(second, EmbeddingResult)
    np.testing.assert_allclose(first.values, second.values)
    u, singular, _ = np.linalg.svd(prepared.values, full_matrices=False)
    expected = u[:, :2] * singular[:2]
    np.testing.assert_allclose(
        first.values @ first.values.T, expected @ expected.T, atol=1e-10
    )
    assert first.provenance.request.seed == 42
    points = prepare_embedding_plot(dataset, first, 10, "z")
    assert len(points.x) == 10 and points.colors is not None
    for row, pos in zip(points.row_ids, points.positions, strict=True):
        assert dataset.row_ids[int(pos)] == row
    full = run_analysis(
        prepare_input(
            dataset,
            AnalysisRequest(
                ("x", "y", "z"), PCAParameters(solver="full"), dimensions=3
            ),
        )
    )
    assert isinstance(full, EmbeddingResult) and full.values.shape == (60, 3)
    plotted = prepare_embedding_plot(dataset, full, 10, None)
    assert plotted.z is not None and plotted.z_name == "PCA 3"
    np.testing.assert_array_equal(plotted.z, full.values[plotted.positions, 2])


def test_kmeans_fit_sample_and_displayed_prediction_alignment() -> None:
    from datelier.analysis.cluster_colors import (
        predict_clusters,
        prepare_cluster_colors,
    )
    from datelier.analysis.types import ClusteringResult, KMeansParameters

    rng = np.random.default_rng(2)
    values = rng.normal(scale=0.15, size=(240, 2)) + np.repeat([0, 10, 20], 80)[:, None]
    dataset = Dataset.from_source(
        pl.DataFrame(values, schema=["x", "y"]), SourceReference(Path("unused"), 0, 0)
    )
    request = AnalysisRequest(("x", "y"), KMeansParameters(), row_limit=30)
    result = run_analysis(prepare_input(dataset, request))
    assert isinstance(result, ClusteringResult)
    assert result.fit is not None
    assert sum(result.counts) == 30 and result.fit.centers.shape == (3, 2)
    labels = predict_clusters(dataset, np.arange(240, dtype=np.uint64), result)
    assert (
        len(set(labels[:80])) == len(set(labels[80:160])) == len(set(labels[160:])) == 1
    )
    assert len(set(labels)) == 3
    fit_labels = labels[result.row_ids]
    np.testing.assert_array_equal(result.labels, fit_labels)
    colors = prepare_cluster_colors(dataset, np.arange(240, dtype=np.uint64), result)
    assert "30 sampled" in colors.note
    repeat = run_analysis(prepare_input(dataset, request))
    assert isinstance(repeat, ClusteringResult)
    np.testing.assert_array_equal(result.labels, repeat.labels)

    # The shared result/color boundary also accepts labels without a predictor.
    from dataclasses import replace

    labels_only = replace(result, fit=None)
    assigned = predict_clusters(dataset, np.arange(240, dtype=np.uint64), labels_only)
    np.testing.assert_array_equal(assigned[result.row_ids], result.labels)
    assert (assigned[np.setdiff1d(np.arange(240), result.row_ids)] == -2).all()
    colors_only = prepare_cluster_colors(
        dataset, np.arange(240, dtype=np.uint64), labels_only
    )
    assert "unseen rows have no assignment" in colors_only.note


def test_tsne_finite_dimensions_seed_and_explicit_settings() -> None:
    from datelier.analysis.types import TSNEParameters

    rng = np.random.default_rng(5)
    dataset = Dataset.from_source(
        pl.DataFrame(rng.normal(size=(40, 3)), schema=["x", "y", "z"]),
        SourceReference(Path("unused"), 0, 0),
    )
    for dimensions in (2, 3):
        request = AnalysisRequest(
            ("x", "y", "z"),
            TSNEParameters(perplexity=5, iterations=300),
            dimensions=dimensions,
        )
        prepared = prepare_input(dataset, request)
        first, second = run_analysis(prepared), run_analysis(prepared)
        assert isinstance(first, EmbeddingResult) and isinstance(
            second, EmbeddingResult
        )
        assert (
            first.values.shape == (40, dimensions) and np.isfinite(first.values).all()
        )
        np.testing.assert_array_equal(first.values, second.values)
        assert first.provenance.request == request


def test_umap_finite_dimensions_seed_and_metric() -> None:
    from datelier.analysis.types import UMAPParameters

    rng = np.random.default_rng(9)
    dataset = Dataset.from_source(
        pl.DataFrame(rng.normal(size=(35, 3)), schema=["x", "y", "z"]),
        SourceReference(Path("unused"), 0, 0),
    )
    for dimensions, metric in ((2, "euclidean"), (3, "cosine")):
        request = AnalysisRequest(
            ("x", "y", "z"),
            UMAPParameters(neighbors=5, metric=metric),
            row_limit=35,
            dimensions=dimensions,
        )
        prepared = prepare_input(dataset, request)
        first, second = run_analysis(prepared), run_analysis(prepared)
        assert isinstance(first, EmbeddingResult) and isinstance(
            second, EmbeddingResult
        )
        assert (
            first.values.shape == (35, dimensions) and np.isfinite(first.values).all()
        )
        np.testing.assert_array_equal(first.values, second.values)
        assert first.provenance.request == request
        assert "umap-learn" in dict(first.provenance.versions)


def test_builder_rejects_different_prepared_settings_before_fit() -> None:
    import pytest

    from datelier.analysis.algorithms.decomposition import PCAAlgorithm

    dataset = Dataset.from_source(
        pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 4.0, 5.0]}),
        SourceReference(Path("unused"), 0, 0),
    )
    prepared = prepare_input(dataset, AnalysisRequest(("x", "y")))
    with pytest.raises(ValueError, match="does not match"):
        PCAAlgorithm(whiten=True).fit(prepared)


def test_clustering_family_uses_its_fitted_space_predictor() -> None:
    from dataclasses import replace

    import pytest
    from numpy.typing import NDArray

    from datelier.analysis.algorithms.clustering import KMeansAlgorithm
    from datelier.analysis.types import ClusteringResult, KMeansFit, KMeansParameters

    class ConstantPredictor(KMeansAlgorithm):
        def predict_values(
            self, values: NDArray[np.float64], fit: KMeansFit
        ) -> NDArray[np.int64]:
            return np.ones(len(values), dtype=np.int64)

    dataset = Dataset.from_source(
        pl.DataFrame({"x": [1.0, 2.0, 3.0, None], "y": [2.0, 4.0, 5.0, 1.0]}),
        SourceReference(Path("unused"), 0, 0),
    )
    parameters = KMeansParameters(clusters=2)
    prepared = prepare_input(dataset, AnalysisRequest(("x", "y"), parameters))
    result = run_analysis(prepared)
    assert isinstance(result, ClusteringResult)
    predictor = ConstantPredictor(clusters=2)
    labels = predictor.predict(dataset, np.arange(4, dtype=np.uint64), result)
    assert labels.tolist() == [1, 1, 1, -2] and not labels.flags.writeable
    # Label-only recipes retain known row assignments, without inventing predictions.
    sampled = predictor.predict(
        dataset, np.arange(4, dtype=np.uint64), replace(result, fit=None)
    )
    assert sampled[-1] == -2
    np.testing.assert_array_equal(sampled[:3], result.labels)
    with pytest.raises(ValueError, match="revision"):
        predictor.predict(
            dataset.with_rows(dataset.table.reverse(), dataset.row_ids.reverse()),
            np.arange(4, dtype=np.uint64),
            result,
        )
    with pytest.raises(ValueError, match="match"):
        KMeansAlgorithm(clusters=1).predict(
            dataset, np.arange(4, dtype=np.uint64), result
        )


def test_one_algorithm_object_owns_tunable_fields_and_fit_facade() -> None:
    from datelier.analysis.algorithms.clustering import KMeansAlgorithm
    from datelier.analysis.types import ClusteringResult

    dataset = Dataset.from_source(
        pl.DataFrame({"x": [0.0, 0.1, 4.0, 4.1, 9.0, 9.1], "y": [0, 1, 4, 5, 9, 10]}),
        SourceReference(Path("unused"), 0, 0),
    )
    method = KMeansAlgorithm(clusters=2, iterations=75)
    first = method.fit(prepare_input(dataset, AnalysisRequest(("x", "y"), method)))
    assert isinstance(first, ClusteringResult) and len(first.counts) == 2
    assert first.provenance.request.parameters is method
    changed = method.with_parameter("clusters", 3)
    second = changed.fit(prepare_input(dataset, AnalysisRequest(("x", "y"), changed)))
    assert isinstance(second, ClusteringResult) and len(second.counts) == 3
    assert changed.iterations == method.iterations == 75
    assert method.clusters == 2
    np.testing.assert_array_equal(first.row_ids, second.row_ids)
    assert isinstance(first.provenance.request.parameters, KMeansAlgorithm)
    assert first.provenance.request.parameters.clusters == 2
