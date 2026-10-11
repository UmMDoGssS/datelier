"""Bounded coordinates and correlations with explicit source identity."""

import math
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.analysis.cluster_colors import prepare_cluster_colors
from datelier.analysis.types import ClusteringResult
from datelier.core import ColumnRole, Dataset, DatasetRevision
from datelier.inspection.profiles import ColumnProfile
from datelier.plotting.colors import PointColors, prepare_colors

CORRELATION_ROW_LIMIT = 10_000


@dataclass(frozen=True)
class Bars:
    positions: NDArray[np.float64]
    counts: NDArray[np.float64]
    labels: tuple[str, ...]
    edges: NDArray[np.float64] = field(
        default_factory=lambda: np.array([], dtype=float)
    )
    tick_labels: tuple[str, ...] = ()


def prepare_bars(profile: ColumnProfile) -> Bars:
    counts = profile.distribution.counts
    labels = profile.distribution.labels
    if profile.other_count:
        counts = (*counts, profile.other_count)
        labels = (*labels, "Other (remaining values)")
    edges = np.array(profile.distribution.edges, dtype=np.float64)
    positions = (
        edges[:-1] + np.diff(edges) / 2
        if len(edges)
        else np.arange(len(counts), dtype=np.float64)
    )
    values = np.array(counts, dtype=np.float64)
    for array in (positions, values, edges):
        array.flags.writeable = False
    return Bars(positions, values, labels, edges, profile.distribution.tick_labels)


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
    z: NDArray[np.float64] | None = None
    z_name: str = ""


def sample_indices(rows: int, limit: int) -> NDArray[np.int64]:
    return np.linspace(0, rows - 1, min(rows, limit), dtype=np.int64)


def feature_columns(dataset: Dataset) -> tuple[str, ...]:
    return dataset.columns_for(ColumnRole.NUMERIC)


def numeric_columns(dataset: Dataset) -> tuple[str, ...]:
    return tuple(
        name for name, dtype in dataset.table.schema.items() if dtype.is_numeric()
    )


def prepare_scatter(
    dataset: Dataset,
    x: str,
    y: str,
    *,
    limit: int = 2_000,
    color: str | None = None,
    clusters: ClusteringResult | None = None,
    z: str | None = None,
) -> Scatter:
    if not 1 <= limit <= 10_000 or x == y:
        raise ValueError(
            "Scatter requires distinct numeric columns and 1–10,000 points"
        )
    if z is not None and (z not in numeric_columns(dataset) or z in (x, y)):
        raise ValueError("3D scatter requires three distinct existing numeric columns")
    table = dataset.table
    if x not in numeric_columns(dataset) or y not in numeric_columns(dataset):
        raise ValueError("Scatter coordinates must be existing numeric columns")
    # Rename user columns before expression-backed Series operations: literal
    # regex-like names and internal-name collisions are ordinary user data.
    xv = table.get_column(x).rename("x").cast(pl.Float64)
    yv = table.get_column(y).rename("y").cast(pl.Float64)
    mask = xv.is_finite() & yv.is_finite()
    zv = table.get_column(z).rename("z").cast(pl.Float64) if z is not None else None
    if zv is not None:
        mask = mask & zv.is_finite()
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
    if zv is not None:
        eligible = eligible.with_columns(zv.filter(mask))
    selected = eligible[sample_indices(eligible.height, limit)]
    xs = selected.get_column("x").to_numpy()
    ys = selected.get_column("y").to_numpy()
    ids = selected.get_column("id").to_numpy()
    positions = selected.get_column("position").to_numpy()
    zs = selected.get_column("z").to_numpy() if zv is not None else None
    if zs is not None:
        for axis in (xs, ys, zs):
            if len(axis) and not math.isfinite(float(axis.max()) - float(axis.min())):
                raise ValueError(
                    "3D coordinate range overflows; use standardized analysis features"
                )
        zs.flags.writeable = False
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
        prepare_cluster_colors(dataset, positions, clusters)
        if clusters is not None
        else prepare_colors(dataset, positions, color)
        if color
        else None,
        zs,
        z or "",
    )


def prepare_correlations(
    dataset: Dataset, *, column_limit: int = 8, features: tuple[str, ...] = ()
) -> tuple[Correlation, ...]:
    if not 2 <= column_limit <= 16:
        raise ValueError("Correlation column limit must be 2–16")
    names = features or feature_columns(dataset)[:column_limit]
    if (
        len(names) > 16
        or len(set(names)) != len(names)
        or any(n not in numeric_columns(dataset) for n in names)
    ):
        raise ValueError("Choose up to 16 distinct numeric relationship columns")
    table = dataset.table
    indices = sample_indices(table.height, CORRELATION_ROW_LIMIT)
    columns = {
        name: table.get_column(name)
        .rename("value")
        .gather(indices)
        .cast(pl.Float64)
        .to_numpy()
        for name in names
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
