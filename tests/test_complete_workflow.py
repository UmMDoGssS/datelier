"""Cross-format inspection, analysis, recipe recovery and explicit export."""

from dataclasses import replace
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import polars as pl
import pytest

from datelier.analysis import run_analysis
from datelier.analysis_input import prepare_input
from datelier.analysis_plots import prepare_embedding_plot
from datelier.analysis_types import (
    AnalysisRequest,
    ClusteringResult,
    EmbeddingResult,
    KMeansParameters,
    Parameters,
    PCAParameters,
    TSNEParameters,
    UMAPParameters,
)
from datelier.clustering import prepare_cluster_colors
from datelier.exploration import PlotSettings, prepare_dashboard
from datelier.inspection import prepare_inspection
from datelier.io.exporting import ExportFormat, export_dataset
from datelier.io.importing import load_file
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Comparison, Filter, Sort
from datelier.pipeline.types import DerivedColumn
from datelier.selection import LinkedSelection
from datelier.workspace_restore import restore_workspace
from datelier.workspace_types import Workspace
from datelier.workspaces import reference_source, save_workspace


def write_source(path: Path) -> None:
    table = pl.DataFrame(
        {
            "x": range(48),
            "y": [None if i == 9 else float(np.sin(i)) for i in range(48)],
            "label": [f"café & <{i}>\nnext" for i in range(48)],
        }
    )
    match path.suffix:
        case ".csv" | ".tsv":
            table.write_csv(path, separator="\t" if path.suffix == ".tsv" else ",")
        case ".json":
            table.write_json(path)
        case ".jsonl":
            table.write_ndjson(path)
        case ".parquet":
            table.write_parquet(path)
        case ".xml":
            records = (
                f"<row><x>{x}</x><y>{'' if y is None else y}</y>"
                f"<label>{escape(label)}</label></row>"
                for x, y, label in table.iter_rows()
            )
            path.write_text("<rows>" + "".join(records) + "</rows>")


@pytest.mark.parametrize(
    ("suffix", "parameters"),
    [
        (suffix, PCAParameters())
        for suffix in ("csv", "tsv", "json", "jsonl", "parquet", "xml")
    ]
    + [
        ("parquet", TSNEParameters(perplexity=5, iterations=250)),
        ("parquet", UMAPParameters(neighbors=5)),
        ("parquet", KMeansParameters(clusters=2)),
    ],
)
def test_complete_workflow(tmp_path: Path, suffix: str, parameters: Parameters) -> None:
    source = tmp_path / f"café source.{suffix}"
    write_source(source)
    original = source.read_bytes()
    imported = load_file(source)
    assert prepare_inspection(imported).first_page.row_ids == tuple(range(48))
    pipeline = (
        Pipeline.start(imported.dataset)
        .apply(Filter("x", Comparison.GE, 5))
        .apply(Sort(("x",), descending=True))
        .apply(DerivedColumn("score", 'col("x") * 2 + col("y")'))
    )
    current = pipeline.current
    assert current.row_ids.to_list() == list(range(47, 4, -1))
    plots = PlotSettings(scatter_pair=("x", "score"), color_column="label", bins=7)
    dashboard = prepare_dashboard(current, plots)
    request = AnalysisRequest(("x", "y", "score"), parameters, row_limit=30, seed=17)
    result = run_analysis(prepare_input(current, request))
    assert result.revision == current.revision
    assert result.provenance.request == request
    assert result.provenance.input.excluded_rows == 1
    assert result.provenance.input.sampled_rows == 30
    assert 9 not in result.row_ids
    points = dashboard.scatters[0]
    if isinstance(result, EmbeddingResult):
        points = prepare_embedding_plot(current, result, 12, "label")
        assert np.isfinite(result.values).all()
        for row, pos in zip(points.row_ids, points.positions, strict=True):
            assert current.row_ids[int(pos)] == row
    else:
        assert isinstance(result, ClusteringResult)
        assert sum(result.counts) == 30
        colors = prepare_cluster_colors(current, points.positions, result)
        assert "30 sampled" in colors.note
    selection = LinkedSelection()
    selection.bind(current.revision)
    assert selection.choose(current.revision, (int(points.row_ids[0]),))
    assert len(selection.overlay(points)[0]) == 1

    # Persist an undo cursor and a valid redo recipe, including analysis settings.
    undone = pipeline.undo()
    recipe = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        pipeline.history,
        undone.cursor,
        (request,),
        plots,
    )
    workspace = tmp_path / "session.datelier"
    save_workspace(workspace, recipe)
    restored = restore_workspace(workspace)
    assert restored.workspace.analysis == (request,)
    assert restored.workspace.plots == plots
    assert restored.pipeline.current.table.equals(undone.current.table)
    redone = restored.pipeline.redo().current
    assert redone.table.equals(current.table)
    assert redone.row_ids.equals(current.row_ids)
    assert redone.revision != current.revision
    selection.bind(redone.revision)
    assert not selection.row_ids and not selection.choose(current.revision, (47,))
    if isinstance(result, EmbeddingResult):
        with pytest.raises(ValueError, match="obsolete"):
            prepare_embedding_plot(redone, result, 12, None)
    assert prepare_dashboard(redone, restored.workspace.plots).scatters
    rerun = run_analysis(prepare_input(redone, restored.workspace.analysis[0]))
    np.testing.assert_array_equal(result.row_ids, rerun.row_ids)
    for format in ExportFormat:
        destination = tmp_path / f"result.{format.name.lower()}"
        export_dataset(redone, destination, format)
        exported = (
            pl.read_csv(destination)
            if format == ExportFormat.CSV
            else pl.read_parquet(destination)
        )
        assert exported.equals(current.table)
    assert source.read_bytes() == original


def test_empty_filtered_workspace_profiles_and_export(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    write_source(source)
    imported = load_file(source)
    original = source.read_bytes()
    pipeline = Pipeline.start(imported.dataset).apply(Filter("x", Comparison.LT, 0))
    current = pipeline.current
    inspection = prepare_inspection(replace(imported, dataset=current))
    assert inspection.first_page.row_ids == ()
    dashboard = prepare_dashboard(current, PlotSettings(scatter_pair=("x", "y")))
    assert not len(dashboard.scatters[0].row_ids)
    with pytest.raises(ValueError, match="at least two eligible"):
        prepare_input(current, AnalysisRequest(("x", "y")))
    workspace = tmp_path / "empty.datelier"
    save_workspace(
        workspace,
        Workspace(
            reference_source(imported.dataset.source),
            imported.format,
            imported.options,
            pipeline.history,
            pipeline.cursor,
        ),
    )
    restored = restore_workspace(workspace)
    assert restored.pipeline.current.table.equals(current.table)
    assert restored.pipeline.undo().current.table.equals(imported.dataset.table)
    for format in ExportFormat:
        destination = tmp_path / format.name
        export_dataset(restored.pipeline.current, destination, format)
        exported = (
            pl.read_csv(destination)
            if format == ExportFormat.CSV
            else pl.read_parquet(destination)
        )
        assert exported.shape == (0, 3)
    assert source.read_bytes() == original
