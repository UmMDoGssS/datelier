from pathlib import Path

import numpy as np
import polars as pl

from datelier.analysis import run_analysis
from datelier.analysis_input import prepare_input
from datelier.analysis_plots import prepare_embedding_plot
from datelier.analysis_types import AnalysisRequest, EmbeddingResult, PCAParameters
from datelier.dataset import Dataset, SourceReference


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


def test_kmeans_fit_sample_and_displayed_prediction_alignment() -> None:
    from datelier.analysis_types import ClusteringResult, KMeansParameters
    from datelier.clustering import predict_clusters, prepare_cluster_colors

    rng = np.random.default_rng(2)
    values = rng.normal(scale=0.15, size=(240, 2)) + np.repeat([0, 10, 20], 80)[:, None]
    dataset = Dataset.from_source(
        pl.DataFrame(values, schema=["x", "y"]), SourceReference(Path("unused"), 0, 0)
    )
    request = AnalysisRequest(("x", "y"), KMeansParameters(), row_limit=30)
    result = run_analysis(prepare_input(dataset, request))
    assert isinstance(result, ClusteringResult)
    assert sum(result.counts) == 30 and result.centers.shape == (3, 2)
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


def test_tsne_finite_dimensions_seed_and_explicit_settings() -> None:
    from datelier.analysis_types import TSNEParameters

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
    from datelier.analysis_types import UMAPParameters

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
