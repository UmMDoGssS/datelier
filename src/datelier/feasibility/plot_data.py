from dataclasses import dataclass

import numpy as np
import polars as pl
from numpy.typing import NDArray


@dataclass(frozen=True)
class ScatterData:
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    row_ids: NDArray[np.uint64]
    eligible_rows: int
    source_rows: int
    x_name: str
    y_name: str


def prepare_scatter(
    table: pl.DataFrame, x: str, y: str, *, limit: int = 10_000
) -> ScatterData:
    """Convert only bounded, finite selected coordinates at the plot boundary."""
    if limit < 1 or x == y:
        raise ValueError("Require a positive point limit and distinct coordinates")
    for name in (x, y):
        if not table.schema[name].is_numeric():
            raise ValueError(f"Coordinate {name!r} must be numeric")
    eligible = table.select("row_id", x, y).filter(
        pl.col(x).is_finite() & pl.col(y).is_finite()
    )
    selected = eligible.head(limit)
    return ScatterData(
        x=selected[x].cast(pl.Float64).to_numpy(),
        y=selected[y].cast(pl.Float64).to_numpy(),
        row_ids=selected["row_id"].cast(pl.UInt64).to_numpy(),
        eligible_rows=eligible.height,
        source_rows=table.height,
        x_name=x,
        y_name=y,
    )
