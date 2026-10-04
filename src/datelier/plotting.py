"""Bounded coordinates and correlations with explicit source identity."""

import math
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.coloring import PointColors, prepare_colors
from datelier.dataset import Dataset, DatasetRevision
from datelier.profiling import ColumnProfile

CORRELATION_ROW_LIMIT = 10_000


@dataclass(frozen=True)
class Bars:
    positions: NDArray[np.float64]
    counts: NDArray[np.float64]
    labels: tuple[str, ...]


def prepare_bars(profile: ColumnProfile) -> Bars:
    counts = profile.distribution.counts
    labels = profile.distribution.labels
    if profile.other_count:
        counts = (*counts, profile.other_count)
        labels = (*labels, "Other (remaining values)")
    return Bars(
        np.arange(len(counts), dtype=np.float64),
        np.array(counts, dtype=np.float64),
        labels,
    )


@dataclass(frozen=True)
class Correlation:
    x_name: str
    y_name: str
    value: float | None
    finite_pairs: int


@dataclass(frozen=True)
class Scatter:
    revision: DatasetRevision
    x_name: str
    y_name: str
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    row_ids: NDArray[np.uint64]
    positions: NDArray[np.uint64]
    eligible_rows: int
    total_rows: int
    colors: PointColors | None = None


def sample_indices(rows: int, limit: int) -> NDArray[np.int64]:
    return np.linspace(0, rows - 1, min(rows, limit), dtype=np.int64)


def numeric_columns(dataset: Dataset) -> tuple[str, ...]:
    return tuple(
        name for name, dtype in dataset.table.schema.items() if dtype.is_numeric()
    )


def prepare_scatter(
    dataset: Dataset, x: str, y: str, *, limit: int = 2_000, color: str | None = None
) -> Scatter:
    if not 1 <= limit <= 10_000 or x == y:
        raise ValueError(
            "Scatter requires distinct numeric columns and 1–10,000 points"
        )
    table = dataset.table
    if x not in numeric_columns(dataset) or y not in numeric_columns(dataset):
        raise ValueError("Scatter coordinates must be existing numeric columns")
    # Rename user columns before expression-backed Series operations: literal
    # regex-like names and internal-name collisions are ordinary user data.
    xv = table.get_column(x).rename("x").cast(pl.Float64)
    yv = table.get_column(y).rename("y").cast(pl.Float64)
    mask = xv.is_finite() & yv.is_finite()
    eligible = pl.DataFrame(
        {
            "x": xv.filter(mask),
            "y": yv.filter(mask),
            "id": dataset.row_ids.filter(mask),
            "position": pl.int_range(
                0, table.height, eager=True, dtype=pl.UInt64
            ).filter(mask),
        }
    )
    selected = eligible[sample_indices(eligible.height, limit)]
    xs = selected.get_column("x").to_numpy()
    ys = selected.get_column("y").to_numpy()
    ids = selected.get_column("id").to_numpy()
    positions = selected.get_column("position").to_numpy()
    for array in (xs, ys, ids, positions):
        array.flags.writeable = False
    return Scatter(
        dataset.revision,
        x,
        y,
        xs,
        ys,
        ids,
        positions,
        eligible.height,
        table.height,
        prepare_colors(dataset, positions, color) if color else None,
    )


def prepare_correlations(
    dataset: Dataset, *, column_limit: int = 8
) -> tuple[Correlation, ...]:
    if not 2 <= column_limit <= 16:
        raise ValueError("Correlation column limit must be 2–16")
    table = dataset.table
    indices = sample_indices(table.height, CORRELATION_ROW_LIMIT)
    columns = {
        name: table.get_column(name)
        .rename("value")
        .gather(indices)
        .cast(pl.Float64)
        .to_numpy()
        for name in numeric_columns(dataset)[:column_limit]
    }
    results = []
    for x, y in combinations(columns, 2):
        xs, ys = columns[x], columns[y]
        mask = np.isfinite(xs) & np.isfinite(ys)
        xs, ys = xs[mask], ys[mask]
        value = None
        if len(xs) >= 2:
            x_scale, y_scale = float(np.max(np.abs(xs))), float(np.max(np.abs(ys)))
            xs = xs / x_scale if x_scale else xs
            ys = ys / y_scale if y_scale else ys
            if np.ptp(xs) > 0 and np.ptp(ys) > 0:
                with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                    correlation = float(np.corrcoef(xs, ys)[0, 1])
                if math.isfinite(correlation):
                    value = correlation
        results.append(Correlation(x, y, value, len(xs)))
    return tuple(results)
