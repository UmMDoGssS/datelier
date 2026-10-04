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
