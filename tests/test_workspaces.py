"""Recipe round trips, strict input handling, and source preservation."""

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from datelier.analysis_types import (
    AnalysisRequest,
    KMeansParameters,
    PCAParameters,
    Preprocessing,
    TSNEParameters,
    UMAPParameters,
)
from datelier.io.importing import load_file
from datelier.io.types import (
    CsvOptions,
    ImportFormat,
    JsonOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.pipeline.history import replay
from datelier.pipeline.operations import Comparison, Filter, SelectColumns, Sort
from datelier.pipeline.types import (
    CastColumn,
    DerivedColumn,
    DropMissing,
    FillMissing,
    Lookup,
    TargetType,
    Unmatched,
)
from datelier.workspace_types import Workspace, WorkspaceViews
from datelier.workspaces import read_workspace, reference_source, save_workspace


def recipe(tmp_path: Path) -> Workspace:
    source = tmp_path / "input.csv"
    source.write_text("x,y\n3,a\n1,b\n2,a\n")
    imported = load_file(source)
    return Workspace(
        reference_source(imported.dataset.source), imported.format, imported.options
    )


def test_reopen_recipe_replays_rows_and_retains_redo(tmp_path: Path) -> None:
    workspace = replace(
        recipe(tmp_path),
        history=(Sort(("x",)), Filter("x", Comparison.GT, 1)),
        cursor=1,
    )
    path = tmp_path / "project.datelier"
    before = Path(workspace.source.path).read_bytes()
    save_workspace(path, workspace)
    saved = read_workspace(path)
    assert saved == workspace
    assert "input.csv" in path.read_text()
    assert str(tmp_path) not in path.read_text()  # portable relative reference
    data = load_file(
        Path(saved.source.path), saved.options, format=saved.format
    ).dataset
    current = replay(data, saved.history[: saved.cursor])
    assert current.table["x"].to_list() == [1, 2, 3]
    assert current.row_ids.to_list() == [1, 2, 0]
    assert Path(workspace.source.path).read_bytes() == before


def test_all_typed_operations_and_analysis_settings_round_trip(tmp_path: Path) -> None:
    workspace = replace(
        recipe(tmp_path),
        history=(
            Sort(("x",), True, False),
            Filter("y", Comparison.EQ, "a"),
            SelectColumns(("x",)),
            CastColumn("x", TargetType.FLOAT, False),
            FillMissing("x", 1.5, True),
            DropMissing(("x",), True),
            Lookup("x", ((None, 0), (True, 2)), TargetType.INT, Unmatched.NULL),
            DerivedColumn("new", 'col("x") * 2', True),
        ),
        cursor=8,
        analysis=tuple(
            AnalysisRequest(("x", "y"), p, Preprocessing(False, True), 12, 100, 3)
            for p in (
                PCAParameters("full", True),
                TSNEParameters(5, 250, 25.0, "random"),
                UMAPParameters(5, 0.2, "cosine"),
                KMeansParameters(2, 3, 50),
            )
        ),
        views=WorkspaceViews("Correlations", 4, 1, 2, 1, 16, 100),
    )
    path = tmp_path / "project.datelier"
    save_workspace(path, workspace)
    assert read_workspace(path) == workspace


@pytest.mark.parametrize(
    "format,options",
    [
        (
            ImportFormat.TSV,
            CsvOptions(separator="\t", null_values=("NA",), infer_schema_length=None),
        ),
        (ImportFormat.JSON, JsonOptions(True)),
        (ImportFormat.JSONL, JsonOptions()),
        (ImportFormat.PARQUET, ParquetOptions(("x", "y"))),
        (
            ImportFormat.XML,
            XmlOptions(
                "./n:row", (("n", "urn:test"),), False, False, ("missing",), False, True
            ),
        ),
    ],
)
def test_import_options_preserved(
    tmp_path: Path, format: ImportFormat, options: object
) -> None:
    from typing import cast

    from datelier.io.types import ImportOptions

    workspace = replace(
        recipe(tmp_path), format=format, options=cast(ImportOptions, options)
    )
    path = tmp_path / "project.datelier"
    save_workspace(path, workspace)
    assert read_workspace(path) == workspace


def test_nonfinite_operation_scalars_have_explicit_json_encoding(
    tmp_path: Path,
) -> None:
    workspace = replace(
        recipe(tmp_path),
        history=(FillMissing("x", float("nan")), FillMissing("y", float("inf"))),
        cursor=2,
    )
    path = tmp_path / "project.datelier"
    save_workspace(path, workspace)
    saved = read_workspace(path)
    first, second = saved.history
    assert (
        isinstance(first, FillMissing)
        and isinstance(first.value, float)
        and math.isnan(first.value)
    )
    assert isinstance(second, FillMissing) and second.value == float("inf")


@pytest.mark.parametrize(
    "edit",
    [
        {"version": 2},
        {"version": True},
        {"cursor": -1},
        {"cursor": "0"},
        {"unexpected": 1},
        {"options": {"kind": "XmlOptions"}},
        {"history": [{"kind": "ExecutePython", "code": "exit()"}]},
        {"plots": {"kind": "PlotSettings", "bins": 0}},
        {"views": {"kind": "WorkspaceViews", "tab": "unknown"}},
        {"analysis": [{"kind": "AnalysisRequest", "features": ["x"], "seed": -1}]},
    ],
)
def test_invalid_workspace_rejected(tmp_path: Path, edit: dict[str, object]) -> None:
    path = tmp_path / "project.datelier"
    save_workspace(path, recipe(tmp_path))
    raw = json.loads(path.read_text())
    raw.update(edit)
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        read_workspace(path)


@pytest.mark.parametrize(
    "content", ["{", '{"kind":"Workspace","kind":"Workspace"}', "NaN", "[]", '"hello"']
)
def test_bad_json_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.datelier"
    path.write_text(content)
    with pytest.raises(ValueError):
        read_workspace(path)


def test_atomic_save_protects_source_and_previous_workspace(tmp_path: Path) -> None:
    workspace = recipe(tmp_path)
    path = tmp_path / "project.datelier"
    save_workspace(path, workspace)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        save_workspace(path, replace(workspace, version=99))
    assert path.read_bytes() == before
    source = Path(workspace.source.path)
    before = source.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        save_workspace(source, workspace)
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    with pytest.raises(ValueError, match="overwrite"):
        save_workspace(alias, workspace)
    assert source.read_bytes() == before


def test_changed_source_cannot_be_saved_as_the_imported_recipe(tmp_path: Path) -> None:
    workspace = recipe(tmp_path)
    imported = load_file(Path(workspace.source.path))
    Path(workspace.source.path).write_text("x\n99\n")
    with pytest.raises(ValueError, match="changed since import"):
        reference_source(imported.dataset.source)


def test_incompatible_shared_analysis_inputs_are_rejected(tmp_path: Path) -> None:
    workspace = replace(
        recipe(tmp_path),
        analysis=(AnalysisRequest(("x",)), AnalysisRequest(("y",), KMeansParameters())),
    )
    with pytest.raises(ValueError, match="share"):
        save_workspace(tmp_path / "project.datelier", workspace)


def test_oversized_recipe_is_rejected_before_json_parsing(tmp_path: Path) -> None:
    from datelier.workspaces import MAX_WORKSPACE_BYTES

    path = tmp_path / "large.datelier"
    path.write_bytes(b" " * (MAX_WORKSPACE_BYTES + 1))
    with pytest.raises(ValueError, match="2 MiB"):
        read_workspace(path)
