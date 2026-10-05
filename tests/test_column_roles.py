from pathlib import Path

import polars as pl
import pytest

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, SourceReference
from datelier.gui_analysis_controls import AnalysisControls
from datelier.gui_plot_controls import PlotControls
from datelier.inspection.profiles import ProfileKind, prepare_profiles
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import OperationFailure, SetColumnRole, Sort
from datelier.plotting.data import prepare_correlations
from datelier.recipe_codec import decode_record, encode


def data() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame(
            {
                "passenger_id": [3, 1, 2, None],
                "name": ["A", "B", "C", None],
                "sex": ["female", "male", "female", None],
                "age": [1, 2, 3, 4],
                "fare": [5.0, 7.0, 9.0, 11.0],
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )


def test_roles_use_nonnull_uniqueness_without_guessing_unique_features() -> None:
    dataset = data()
    assert dataset.role("passenger_id").role == ColumnRole.IDENTIFIER
    assert dataset.role("name").role == ColumnRole.TEXT
    assert dataset.role("name").distinct == 3
    assert dataset.role("sex").role == ColumnRole.CATEGORY
    assert dataset.role("age").role == ColumnRole.NUMERIC
    assert {p.name for p in prepare_profiles(dataset).columns} == {"sex", "age", "fare"}
    profiles = {
        name: prepare_profiles(dataset, column=name).columns[0]
        for name in dataset.table.columns
    }
    assert profiles["name"].kind == ProfileKind.TEXT
    assert not profiles["name"].distribution.counts
    assert not profiles["passenger_id"].distribution.counts
    assert profiles["sex"].distribution.counts == (2, 1)
    assert len(prepare_correlations(dataset)) == 1
    plots, analysis = PlotControls(), AnalysisControls()
    plots.bind(dataset)
    analysis.bind(dataset)
    assert plots.numeric == analysis.numeric == ("age", "fare")
    assert plots.color_columns == ("sex", "age", "fare")


def test_role_override_is_replayable_reversible_and_preserves_values_and_ids() -> None:
    original = data()
    operation = SetColumnRole("passenger_id", ColumnRole.NUMERIC)
    assert decode_record(SetColumnRole, encode(operation)) == operation
    pipeline = Pipeline.start(original).apply(operation).apply(Sort(("age",), True))
    assert pipeline.current.role("passenger_id").override == ColumnRole.NUMERIC
    assert pipeline.current.row_ids.to_list() == [3, 2, 1, 0]
    assert pipeline.current.revision != original.revision
    restored = pipeline.undo().undo()
    assert restored.current.role("passenger_id").role == ColumnRole.IDENTIFIER
    assert restored.redo().current.role("passenger_id").role == ColumnRole.NUMERIC
    assert original.table.equals(data().table)
    assert original.row_ids.to_list() == [0, 1, 2, 3]
    category = pipeline.apply(SetColumnRole("age", ColumnRole.CATEGORY)).current
    assert (
        prepare_profiles(category, column="age").columns[0].kind
        == ProfileKind.CATEGORICAL
    )
    automatic = pipeline.apply(SetColumnRole("passenger_id")).current
    assert automatic.role("passenger_id").role == ColumnRole.IDENTIFIER
    with pytest.raises(OperationFailure):
        pipeline.apply(SetColumnRole("name", ColumnRole.NUMERIC))


def test_explicit_categories_and_empty_text_are_not_misclassified() -> None:
    dataset = Dataset.from_source(
        pl.DataFrame(
            {
                "group": pl.Series(["a", "b"], dtype=pl.Enum(["a", "b"])),
                "empty": pl.Series([None, None], dtype=pl.String),
                "customerID": [1, 2],
                "id": [7, 7],
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )
    assert dataset.role("group").role == ColumnRole.CATEGORY
    assert dataset.role("empty").role == ColumnRole.CATEGORY
    assert dataset.role("customerID").role == ColumnRole.IDENTIFIER
    assert dataset.role("id").role == ColumnRole.NUMERIC


def test_role_overrides_survive_workspace_restore(tmp_path: Path) -> None:
    from datelier.io.importing import load_file
    from datelier.workspace_restore import restore_workspace
    from datelier.workspace_types import Workspace
    from datelier.workspaces import reference_source, save_workspace

    path = tmp_path / "source.csv"
    path.write_text("id,group\n1,a\n2,b\n3,a\n")
    imported = load_file(path)
    pipeline = Pipeline.start(imported.dataset).apply(
        SetColumnRole("id", ColumnRole.NUMERIC)
    )
    workspace = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        pipeline.history,
        pipeline.cursor,
    )
    saved = tmp_path / "roles.datelier"
    save_workspace(saved, workspace)
    restored = restore_workspace(saved).pipeline
    assert restored.current.role("id").role == ColumnRole.NUMERIC
    assert restored.undo().current.role("id").role == ColumnRole.IDENTIFIER
    assert restored.current.table.equals(imported.dataset.table)
