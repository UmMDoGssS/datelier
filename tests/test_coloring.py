from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl

from datelier.core.dataset import Dataset, SourceReference
from datelier.plotting.colors import NEUTRAL, prepare_colors
from datelier.plotting.data import prepare_scatter


def test_color_alignment_after_reordering_and_nonfinite() -> None:
    data = Dataset.from_source(
        pl.DataFrame(
            {"x": [1.0, 2.0, 3.0], "y": [3.0, 2.0, 1.0], "c": [1.0, float("nan"), 9.0]}
        ),
        SourceReference(Path("unused"), 0, 0),
    )
    original = prepare_scatter(data, "x", "y", color="c")
    assert original.colors is not None
    assert original.colors.rgba[1] == NEUTRAL
    reverse = data.with_rows(data.table.reverse(), data.row_ids.reverse())
    result = prepare_scatter(reverse, "x", "y", color="c")
    assert result.colors is not None
    assert dict(zip(original.row_ids, original.colors.rgba, strict=True)) == dict(
        zip(result.row_ids, result.colors.rgba, strict=True)
    )


def test_categories_missing_other_and_temporal_precision() -> None:
    table = pl.DataFrame({"c": [str(i) for i in range(14)] + [None]})
    data = Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))
    colors = prepare_colors(data, np.arange(15, dtype=np.uint64), "c")
    assert len(colors.legend) == 14
    assert colors.rgba[-1] == NEUTRAL
    assert "Other" in dict(colors.legend)
    temporal = pl.Series(
        "t", [datetime(2024, 1, 1)] * 2, dtype=pl.Datetime("ns")
    ).to_physical()
    temporal = (temporal + pl.Series([0, 1])).cast(pl.Datetime("ns"))
    data = Dataset.from_source(temporal.to_frame(), data.source)
    colors = prepare_colors(data, np.array([0, 1], dtype=np.uint64), "t")
    assert colors.rgba[0] != colors.rgba[1]
