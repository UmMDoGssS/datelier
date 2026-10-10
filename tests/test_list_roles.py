import json
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from datelier.core.column_roles import ColumnRole, allowed_roles
from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.profile_preview import ProfileRequest, prepare_profile_group
from datelier.inspection.profiles import ProfileKind
from datelier.io.importing import load_file
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import OperationFailure, SetColumnRole, Sort
from datelier.plotting.data import numeric_columns
from datelier.plotting.distributions import DistributionSettings
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.restore import restore_recipe
from datelier.workspace.storage import reference_source
from datelier.workspace.types import Workspace


def test_list_meanings_follow_leaf_type_and_bounded_text_evidence() -> None:
    table = pl.DataFrame(
        {
            "numbers": [[1, 2], [3]],
            "tags": [["red", "blue"], ["red"]],
            "prose": [["one two three", "four five six"], ["seven eight nine"]],
            "flags": [[True, False], [True]],
            "objects": [[{"x": 1}], []],
            "dates": [[date(2026, 10, 10)], [date(2026, 10, 11)]],
            "nested": [[["one two three"]], [["four five six"]]],
        }
    )
    dataset = Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))
    assert [i.role for i in dataset.roles or ()] == [
        ColumnRole.LIST_NUMERIC,
        ColumnRole.LIST_CATEGORY,
        ColumnRole.LIST_TEXT,
        ColumnRole.LIST_CATEGORY,
        ColumnRole.LIST_OBJECT,
        ColumnRole.LIST_TEMPORAL,
        ColumnRole.LIST_TEXT,
    ]
    assert (
        "2/2" in dataset.role("nested").reason and "256" in dataset.role("prose").reason
    )
    assert numeric_columns(dataset) == ()
    late = Dataset.from_source(
        pl.DataFrame({"text": [["one two three"] * 256 + ["tag"] * 5000]}),
        dataset.source,
    )
    assert late.role("text").role == ColumnRole.LIST_TEXT
    assert "256/256" in late.role("text").reason


def test_list_overrides_are_typed_reversible_and_restore_source_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.json"
    content = json.dumps(
        [
            {"id": 2, "values": [2, 2, 1], "text": ["a", "b"]},
            {"id": 1, "values": [1], "text": ["c"]},
        ]
    )
    path.write_text(content)
    imported = load_file(path)
    operation = SetColumnRole("values", ColumnRole.LIST_CATEGORY)
    assert decode_record(SetColumnRole, encode(operation)) == operation
    pipeline = Pipeline.start(imported.dataset).apply(operation).apply(Sort(("id",)))
    group = prepare_profile_group(
        pipeline.current, ProfileRequest(DistributionSettings(("values",)))
    )
    profile = group.profiles.columns[0]
    assert profile.kind == ProfileKind.CATEGORICAL and profile.statistics is None
    assert profile.distribution.labels == (
        "1",
        "2",
    ) and profile.distribution.counts == (2, 2)
    assert group.comparison is None
    assert pipeline.current.role("values").override == ColumnRole.LIST_CATEGORY
    assert pipeline.current.row_ids.to_list() == [1, 0]
    assert pipeline.undo().undo().current.role("values").role == ColumnRole.LIST_NUMERIC
    assert (
        pipeline.undo().redo().current.role("values").role == ColumnRole.LIST_CATEGORY
    )
    recipe = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        pipeline.history,
        pipeline.cursor,
    )
    restored = restore_recipe(decode_record(Workspace, encode(recipe)))
    assert restored.inspection.dataset.role("values").role == ColumnRole.LIST_CATEGORY
    assert restored.inspection.dataset.table.equals(pipeline.current.table)
    assert restored.inspection.dataset.row_ids.equals(pipeline.current.row_ids)
    legacy = pipeline.apply(SetColumnRole("values", ColumnRole.LIST)).current
    assert (
        prepare_profile_group(legacy, ProfileRequest(DistributionSettings(("values",))))
        .profiles.columns[0]
        .kind
        == ProfileKind.NUMERIC
    )
    assert path.read_text() == content
    text = pipeline.apply(SetColumnRole("text", ColumnRole.LIST_TEXT)).current
    assert text.role("text").role == ColumnRole.LIST_TEXT
    assert text.table.equals(pipeline.current.table)
    assert ColumnRole.LIST_TEXT not in allowed_roles(pl.List(pl.Int64))
    with pytest.raises(OperationFailure, match="incompatible"):
        pipeline.apply(SetColumnRole("values", ColumnRole.LIST_TEXT))
    identifiers = pipeline.apply(
        SetColumnRole("values", ColumnRole.LIST_IDENTIFIER)
    ).current
    identifier = prepare_profile_group(
        identifiers, ProfileRequest(DistributionSettings(("values",)))
    ).profiles.columns[0]
    assert (
        identifier.kind == ProfileKind.IDENTIFIER and not identifier.distribution.counts
    )
