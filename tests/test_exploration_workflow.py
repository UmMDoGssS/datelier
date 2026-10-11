from pathlib import Path

import polars as pl
import pytest

from datelier.analysis.cluster_colors import predict_clusters
from datelier.analysis.input import prepare_input
from datelier.analysis.plots import prepare_embedding_plot
from datelier.analysis.runner import run_analysis
from datelier.analysis.types import (
    AnalysisRequest,
    ClusteringResult,
    EmbeddingResult,
    KMeansParameters,
)
from datelier.inspection.exploration import PlotSettings, prepare_dashboard
from datelier.io.importing import load_file
from datelier.pipeline import Comparison, Filter, Pipeline, Sort
from datelier.plotting.scatter import LinkedSelection


@pytest.mark.parametrize("suffix", ["csv", "tsv", "json", "jsonl", "parquet", "xml"])
def test_format_to_profile_transform_sample_selection(
    tmp_path: Path, suffix: str
) -> None:
    table = pl.DataFrame(
        {"x": [3.0, 1.0, 2.0], "y": [6, 2, 4], "label": ["b", "a", "a"]}
    )
    path = tmp_path / f"source.{suffix}"
    if suffix in ("csv", "tsv"):
        table.write_csv(path, separator="\t" if suffix == "tsv" else ",")
    elif suffix == "json":
        table.write_json(path)
    elif suffix == "jsonl":
        table.write_ndjson(path)
    elif suffix == "parquet":
        table.write_parquet(path)
    else:
        path.write_text(
            "<rows>"
            + "".join(
                f"<row><x>{x}</x><y>{y}</y><label>{label}</label></row>"
                for x, y, label in table.iter_rows()
            )
            + "</rows>"
        )
    original = path.read_bytes()
    imported = load_file(path)
    before = prepare_dashboard(imported.dataset)
    assert before.profiles.columns[0].mean == pytest.approx(2)
    assert before.profiles.columns[2].distribution.counts == (2, 1)
    pipeline = (
        Pipeline.start(imported.dataset)
        .apply(Sort(("x",)))
        .apply(Filter("x", Comparison.GE, 2))
    )
    after = prepare_dashboard(pipeline.current, PlotSettings(point_limit=1))
    points = after.scatters[0]
    assert points.row_ids.tolist() == [2] and points.positions.tolist() == [0]
    assert points.eligible_rows == 2 and points.total_rows == 2
    assert after.correlations[0].value == pytest.approx(1)
    selection = LinkedSelection()
    selection.bind(pipeline.current.revision)
    assert selection.nearest(points, 2, 4, 10, 10) == 0
    assert selection.row_ids == {2}
    assert not selection.rectangle(before.scatters[0], 0, 0, 10, 10)
    restored = pipeline.undo().undo().current
    selection.bind(restored.revision)
    assert not selection.row_ids
    assert prepare_dashboard(restored).scatters[0].row_ids.tolist() == [0, 1, 2]
    embedding = run_analysis(
        prepare_input(pipeline.current, AnalysisRequest(("x", "y")))
    )
    assert isinstance(embedding, EmbeddingResult)
    plotted = prepare_embedding_plot(pipeline.current, embedding, 2, None)
    assert plotted.row_ids.tolist() == [0, 2]
    cluster = run_analysis(
        prepare_input(
            pipeline.current, AnalysisRequest(("x", "y"), KMeansParameters(clusters=2))
        )
    )
    assert isinstance(cluster, ClusteringResult)
    labels = predict_clusters(pipeline.current, plotted.positions, cluster)
    assert len(set(labels)) == 2
    assert path.read_bytes() == original
