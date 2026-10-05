"""Bounded numeric distributions within source-aligned category groups."""

import math
from dataclasses import dataclass, replace

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.core.dataset import Dataset
from datelier.plotting.distributions import (
    DistributionSettings,
    NumericDistribution,
    prepare_comparison,
)
from datelier.plotting.selection import SELECTION_LIMIT


@dataclass(frozen=True)
class CategoryDistributions:
    series: tuple[NumericDistribution, ...]
    values: NDArray[np.float64]
    counts: NDArray[np.int64]
    row_ids: tuple[tuple[int, ...], ...]
    first_positions: tuple[int, ...]
    scale: float


def prepare_category_distributions(
    dataset: Dataset,
    frame: pl.DataFrame,
    labels: tuple[str, ...],
    value_column: str,
    bandwidth: float,
    seed: int,
) -> CategoryDistributions:
    # `frame` has already excluded nonfinite values and assigned category codes.
    minimum, maximum = frame.get_column("value").min(), frame.get_column("value").max()
    scale = 1.0
    if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)):
        magnitude = max(abs(minimum), abs(maximum))
        if not math.isfinite(maximum - minimum) or magnitude >= 1e300:
            scale = float(magnitude)
            frame = frame.with_columns(pl.col("value") / scale)
    series: list[NumericDistribution] = []
    row_ids: list[tuple[int, ...]] = []
    positions: list[int] = []
    for code, label in enumerate(labels):
        group = frame.filter(pl.col("c") == code)
        cohort = Dataset(
            dataset.source,
            dataset.revision,
            dataset.source_row_count,
            group.select(pl.col("value").alias(value_column)),
            group.get_column("row_id"),
            (dataset.role(value_column),),
        )
        prepared = prepare_comparison(
            cohort,
            DistributionSettings((value_column,), bandwidth=bandwidth, seed=seed),
            # Boxes/violins do not use histogram bins. One interval avoids
            # needless bin precision failures for close, large measurements.
            bins=1,
        ).series[0]
        series.append(replace(prepared, name=label))
        row_ids.append(
            tuple(group.get_column("row_id").head(SELECTION_LIMIT).to_list())
        )
        position = group.get_column("position").first()
        positions.append(int(position) if isinstance(position, int) else 0)
    values = np.array([[s.box[2] if s.box else 0 for s in series]], dtype=np.float64)
    counts = np.array([[s.count for s in series]], dtype=np.int64)
    values.flags.writeable = counts.flags.writeable = False
    return CategoryDistributions(
        tuple(series), values, counts, tuple(row_ids), tuple(positions), scale
    )
