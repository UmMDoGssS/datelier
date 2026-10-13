"""Wide facts preserve values and compared series have separated saturated hues."""

from colorsys import rgb_to_hsv
from pathlib import Path

import polars as pl
import pytest

from datelier.core import Dataset, SourceReference
from datelier.gui.profiles.distributions.colors import profile_color
from datelier.inspection.profiles import prepare_profiles
from datelier.inspection.profiles.preview import ProfileRequest, prepare_profile_group
from datelier.inspection.profiles.tables import prepare_statistics_tables
from datelier.plotting.distributions import DistributionSettings


def dataset(table: pl.DataFrame) -> Dataset:
    return Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))


def test_numeric_facts_are_one_row_per_column_with_original_statistics() -> None:
    data = dataset(pl.DataFrame({"x": [1.0, 3.0, None], "y": [2.0, 4.0, 6.0]}))
    group = prepare_profile_group(
        data, ProfileRequest(DistributionSettings(("x", "y")))
    )
    table = group.tables[0]
    assert table.headers[0] == "Column" and len(set(table.headers)) == len(
        table.headers
    )
    rows = [dict(zip(table.headers, row, strict=True)) for row in table.rows]
    assert [row["Column"] for row in rows] == ["x", "y"]
    assert (rows[0]["Mean"], rows[0]["Non-null"], rows[0]["Null"]) == (2, 2, 1)
    assert (rows[1]["Mean"], rows[1]["Median"], rows[1]["Std"]) == (4, 4, 2)
    empty = dataset(pl.DataFrame({"x": [None, None]}, schema={"x": pl.Float64}))
    facts = prepare_statistics_tables(prepare_profiles(empty))[0]
    row = dict(zip(facts.headers, facts.rows[0], strict=True))
    assert row["Mean"] is None and row["Null"] == 2
    large = dataset(pl.DataFrame({"id": [1, 2], "big": [2**53 + 1, 2**53 + 2]}))
    facts = prepare_statistics_tables(prepare_profiles(large, column="big"))[0]
    row = dict(zip(facts.headers, facts.rows[0], strict=True))
    assert row["Minimum"] == 2**53 + 1 and row["Maximum"] == 2**53 + 2


def test_category_and_list_facts_keep_quality_lengths_and_shapes_separate() -> None:
    data = dataset(
        pl.DataFrame(
            {"category": ["a", "a", None], "lists": [[[1, 2]], [[3], [4, 5]], None]}
        )
    )
    category = prepare_statistics_tables(prepare_profiles(data, column="category"))[0]
    row = dict(zip(category.headers, category.rows[0], strict=True))
    assert (row["Non-null"], row["Unique"], row["Null"]) == (2, 1, 1)
    tables = {
        table.key: table
        for table in prepare_statistics_tables(prepare_profiles(data, column="lists"))
    }
    assert len(tables["statistics"].rows) == 1
    values = dict(
        zip(tables["statistics"].headers, tables["statistics"].rows[0], strict=True)
    )
    assert values["Mean"] == 3 and values["Non-null"] == 5
    lengths = tables["list-lengths"]
    assert len(lengths.rows) == 2
    outer = dict(zip(lengths.headers, lengths.rows[0], strict=True))
    assert (outer["Column"], outer["Depth"], outer["Containers"], outer["Null"]) == (
        "lists",
        1,
        3,
        1,
    )
    assert ("lists", "ragged", 1) in tables["list-shapes"].rows


@pytest.mark.parametrize("count", [2, 3, 8, 16, 32])
def test_compared_colors_maximize_hue_spacing_and_ignore_series_order(
    count: int,
) -> None:
    names = tuple(f"column-{i}" for i in range(count))
    hues: list[float] = []
    for name in names:
        color = profile_color(name, names)
        reordered = profile_color(name, tuple(reversed(names)))
        assert (color.x, color.y, color.z) == (reordered.x, reordered.y, reordered.z)
        hue, saturation, value = rgb_to_hsv(color.x, color.y, color.z)
        hues.append(hue)
        assert saturation >= 0.77 and value >= 0.94
    hues.sort()
    gaps = [b - a for a, b in zip(hues[:-1], hues[1:], strict=True)] + [
        1 + hues[0] - hues[-1]
    ]
    assert gaps == pytest.approx([1 / count] * count, abs=1e-6)
    color, repeated = (
        profile_color(names[0], names),
        profile_color(names[0], (*names, names[0])),
    )
    assert (color.x, color.y, color.z) == (repeated.x, repeated.y, repeated.z)
