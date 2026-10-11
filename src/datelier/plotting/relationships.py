"""Bounded relationship matrix with shared, correctly oriented pair data."""

from dataclasses import dataclass, replace
from itertools import combinations

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.core import Dataset
from datelier.inspection.profiles import ProfileKind, prepare_range_profile
from datelier.plotting.distributions import (
    Comparison,
    DistributionSettings,
    prepare_comparison,
)
from datelier.plotting.scatter.prepare import (
    CORRELATION_ROW_LIMIT,
    Bars,
    Correlation,
    Scatter,
    prepare_bars,
    prepare_scatter,
    sample_indices,
)


@dataclass(frozen=True)
class Relationships:
    names: tuple[str, ...]
    values: NDArray[np.float64]
    finite_counts: NDArray[np.int64]
    cells: tuple[tuple[Scatter | None, ...], ...]
    diagonals: tuple[Bars, ...]
    sampled_rows: int
    total_rows: int
    diagonal_mode: int = 0
    diagonal_distributions: tuple[Comparison | None, ...] = ()
    diagonal_notes: tuple[str, ...] = ()


def prepare_relationships(
    dataset: Dataset,
    names: tuple[str, ...],
    correlations: tuple[Correlation, ...],
    bins: int,
    diagonal_mode: int = 0,
    bandwidth: float = 1,
    seed: int = 42,
) -> Relationships:
    n = len(names)
    matrix = np.full((n, n), np.nan, dtype=np.float64)
    counts = np.zeros((n, n), dtype=np.int64)
    indices = sample_indices(dataset.table.height, CORRELATION_ROW_LIMIT)
    cohort = Dataset(
        dataset.source,
        dataset.revision,
        dataset.source_row_count,
        dataset.table[indices],
        dataset.row_ids.gather(indices),
        dataset.roles,
    )
    for i, name in enumerate(names):
        finite = cohort.table.get_column(name).cast(pl.Float64)
        finite = finite.filter(finite.is_finite())
        counts[i, i] = len(finite)
        if len(finite) >= 2 and finite.n_unique() > 1:
            matrix[i, i] = 1
    for correlation in correlations:
        i, j = names.index(correlation.x_name), names.index(correlation.y_name)
        matrix[i, j] = matrix[j, i] = (
            correlation.value if correlation.value is not None else np.nan
        )
        counts[i, j] = counts[j, i] = correlation.finite_pairs
    cells: list[list[Scatter | None]] = [[None] * n for _ in names]
    diagonals: tuple[Bars, ...] = ()
    distributions: list[Comparison | None] = []
    notes: list[str] = []
    if n <= 8:
        for i, j in combinations(range(n), 2):
            points = prepare_scatter(cohort, names[j], names[i], limit=150)
            # Map cohort positions back to current table positions, not row IDs.
            positions = indices[points.positions].astype(np.uint64)
            positions.flags.writeable = False
            points = replace(
                points, positions=positions, total_rows=dataset.table.height
            )
            cells[i][j] = points
            cells[j][i] = replace(
                points,
                x_name=points.y_name,
                y_name=points.x_name,
                x=points.y,
                y=points.x,
            )
        diagonals = tuple(
            prepare_bars(
                prepare_range_profile(
                    dataset.table.get_column(name), ProfileKind.NUMERIC, bins
                )
            )
            for name in names
        )
        if diagonal_mode:
            for name in names:
                try:
                    comparison = prepare_comparison(
                        dataset,
                        DistributionSettings((name,), bandwidth=bandwidth, seed=seed),
                        bins,
                    )
                    distributions.append(comparison)
                    notes.append(comparison.series[0].note)
                except ValueError as error:
                    distributions.append(None)
                    notes.append(str(error))
    matrix.flags.writeable = counts.flags.writeable = False
    return Relationships(
        names,
        matrix,
        counts,
        tuple(tuple(row) for row in cells),
        diagonals,
        len(indices),
        dataset.table.height,
        diagonal_mode,
        tuple(distributions),
        tuple(notes),
    )
