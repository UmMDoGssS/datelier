from pathlib import Path
from threading import Event
from time import monotonic, sleep

import numpy as np
import polars as pl
import pytest

from datelier.dataset import Dataset, SourceReference
from datelier.exploration import Dashboard, Explorer, PlotSettings, prepare_dashboard
from datelier.operations import Comparison, Filter, Sort
from datelier.pipeline import Pipeline
from datelier.plotting import prepare_correlations, prepare_scatter


def dataset(table: pl.DataFrame) -> Dataset:
    return Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))


def test_known_correlations_and_suggestions() -> None:
    data = dataset(
        pl.DataFrame(
            {
                "x": [1.0, 2.0, 3.0, None, float("inf")],
                "y": [2.0, 4.0, 6.0, 8.0, 10.0],
                "constant": [1] * 5,
                "category": ["a"] * 5,
            }
        )
    )
    result = prepare_dashboard(data)
    assert result.correlations[0].value == pytest.approx(1)
    assert result.correlations[0].finite_pairs == 3
    assert all(c.value is None for c in result.correlations[1:])
    scatter = result.scatters[0]
    assert scatter.row_ids.tolist() == [0, 1, 2]
    assert scatter.eligible_rows == 3 and scatter.total_rows == 5
    assert result.revision == scatter.revision == data.revision


def test_sorted_filtered_sampled_identity_and_literal_names() -> None:
    data = dataset(pl.DataFrame({"^x$": range(20), "id": range(20)}))
    transformed = (
        Pipeline.start(data)
        .apply(Sort(("id",), descending=True))
        .apply(Filter("id", Comparison.GE, 5))
        .current
    )
    points = prepare_scatter(transformed, "^x$", "id", limit=4)
    assert points.row_ids.tolist() == [19, 15, 10, 5]
    np.testing.assert_array_equal(points.x, points.row_ids)
    assert not points.x.flags.writeable
    assert prepare_correlations(transformed)[0].value == pytest.approx(1)
    with pytest.raises(ValueError):
        prepare_scatter(data, "id", "id")


def test_empty_unsupported_wide_and_configuration() -> None:
    empty = dataset(
        pl.DataFrame(
            {"x": pl.Series([], dtype=pl.Float64), "y": pl.Series([], dtype=pl.Float64)}
        )
    )
    assert len(prepare_scatter(empty, "x", "y").x) == 0
    assert not prepare_dashboard(empty).scatters
    wide = dataset(pl.DataFrame({f"x{i}": range(10) for i in range(80)}))
    default = prepare_dashboard(wide)
    assert len(default.correlations) == 28 and len(default.scatters) == 3
    expanded = prepare_dashboard(
        wide,
        PlotSettings(
            correlation_columns=16, scatter_pair=("x78", "x79"), point_limit=4
        ),
    )
    assert len(expanded.correlations) == 120 and expanded.scatters[0].x_name == "x78"
    with pytest.raises(ValueError):
        prepare_dashboard(wide, PlotSettings(correlation_columns=17))
    bad = dataset(pl.DataFrame({"x": ["a"], "y": [1]}))
    with pytest.raises(ValueError):
        prepare_scatter(bad, "x", "y")
    assert not prepare_dashboard(bad).scatters


def wait(explorer: Explorer, data: Dataset) -> None:
    deadline = monotonic() + 3
    while explorer.busy and monotonic() < deadline:
        explorer.poll(data.revision)
        sleep(0.001)
    assert not explorer.busy


def test_background_failure_stale_abandon_and_newer_request(monkeypatch) -> None:
    import datelier.exploration as module

    old = dataset(pl.DataFrame({"x": [1, 2], "y": [2, 4]}))
    new = dataset(pl.DataFrame({"x": [3, 4], "y": [6, 8]}))
    started, release = Event(), Event()
    original = module.prepare_dashboard

    def slow(data: Dataset, settings: PlotSettings) -> Dashboard:
        if data is old:
            started.set()
            assert release.wait(3)
        return original(data, settings)

    monkeypatch.setattr(module, "prepare_dashboard", slow)
    explorer = Explorer()
    try:
        explorer.request(old)
        assert started.wait(3)
        assert not explorer.poll(old.revision)
        explorer.request(new)
        wait(explorer, new)
        assert explorer.active is not None and explorer.active.revision == new.revision
        release.set()
        explorer.poll(new.revision)
        assert explorer.active.revision == new.revision
        explorer.request(old)
        wait(explorer, new)
        assert explorer.active is None and "obsolete" in explorer.message
        explorer.request(new, PlotSettings(scatter_pair=("x", "missing")))
        wait(explorer, new)
        assert "failed" in explorer.message
        explorer.request(new)
        explorer.abandon()
        explorer.poll(new.revision)
        assert explorer.active is None
    finally:
        release.set()
        explorer.close()
