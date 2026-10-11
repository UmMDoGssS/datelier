"""Bounded categorical aggregates and source-row groups, prepared in workers."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, DatasetRevision
from datelier.inspection.profiles import COUNT_ROW_LIMIT
from datelier.plotting.distributions import (
    DistributionSettings,
    NumericDistribution,
    prepare_category_distributions,
)
from datelier.plotting.scatter import SELECTION_LIMIT


class CategoryRepresentation(StrEnum):
    COUNTS = "Count bars"
    GROUPED = "Grouped count bars"
    MEAN = "Mean bars"
    MEDIAN = "Median bars"
    SUM = "Sum bars"
    BOX = "Box"
    VIOLIN = "Violin"


@dataclass(frozen=True)
class CategorySettings:
    category: str
    representation: CategoryRepresentation = CategoryRepresentation.COUNTS
    value: str | None = None
    group: str | None = None
    top: int = 12
    bandwidth: float = 1.0
    seed: int = 42

    def validate(self) -> None:
        DistributionSettings(bandwidth=self.bandwidth, seed=self.seed).validate()
        if not self.category or not 1 <= self.top <= 30:
            raise ValueError("Choose a category and 1–30 visible categories")
        if self.representation == CategoryRepresentation.GROUPED:
            if not self.group or self.group == self.category or self.value is not None:
                raise ValueError("Choose two distinct category columns")
        elif self.representation == CategoryRepresentation.COUNTS:
            if self.value is not None or self.group is not None:
                raise ValueError("Counts use one category column")
        elif not self.value or self.group is not None:
            raise ValueError("Choose a numeric value column")


@dataclass(frozen=True)
class CategoryChart:
    revision: DatasetRevision
    settings: CategorySettings
    labels: tuple[str, ...]
    groups: tuple[str, ...]
    values: NDArray[np.float64]
    counts: NDArray[np.int64]
    row_ids: tuple[tuple[tuple[int, ...], ...], ...]
    first_positions: tuple[tuple[int, ...], ...]
    included_rows: int
    input_rows: int
    total_rows: int
    excluded_values: int
    other_categories: int
    other_groups: int
    distributions: tuple[NumericDistribution, ...] = ()
    distribution_scale: float = 1.0

    @property
    def value_label(self) -> str:
        representation = self.settings.representation
        if representation in (
            CategoryRepresentation.BOX,
            CategoryRepresentation.VIOLIN,
        ):
            return (
                f"{self.settings.value} / {self.distribution_scale:.6g}"
                if self.distribution_scale != 1
                else str(self.settings.value)
            )
        if representation in (
            CategoryRepresentation.COUNTS,
            CategoryRepresentation.GROUPED,
        ):
            return "Rows"
        return f"{representation.value.split()[0]} of {self.settings.value}"


def _codes(
    frame: pl.DataFrame, column: str, top: int
) -> tuple[pl.Expr, tuple[str, ...], int]:
    counts = (
        frame.group_by(column)
        .len()
        .sort(["len", column], descending=[True, False], nulls_last=True)
    )
    keys = counts.head(top).get_column(column)
    other = max(0, counts.height - top)
    labels: list[str] = []
    for key in keys:
        label = "Missing (null)" if key is None else str(key)
        if len(label) > 80:
            label = label[:77] + "…"
        if label in labels or label == "Other (remaining values)":
            label += f" [{len(labels) + 1}]"
        labels.append(label)
    if other:
        labels.append("Other (remaining values)")
    return (
        pl.col(column).replace_strict(
            keys, pl.Series(range(len(keys)), dtype=pl.Int64), default=len(keys)
        ),
        tuple(labels),
        other,
    )


def prepare_category_chart(
    dataset: Dataset, settings: CategorySettings
) -> CategoryChart:
    settings.validate()
    if dataset.role(settings.category).role != ColumnRole.CATEGORY:
        raise ValueError(
            "Choose a categorical column; change its role in Schema if needed"
        )
    if settings.group and dataset.role(settings.group).role != ColumnRole.CATEGORY:
        raise ValueError("Grouping requires a categorical column")
    if settings.value and dataset.role(settings.value).role != ColumnRole.NUMERIC:
        raise ValueError("Aggregation requires a numeric feature")
    table = dataset.table.head(COUNT_ROW_LIMIT)
    columns = [
        table.get_column(settings.category).cast(pl.String).alias("category"),
        dataset.row_ids.head(COUNT_ROW_LIMIT).alias("row_id"),
        pl.Series("position", range(table.height), dtype=pl.UInt64),
    ]
    if settings.group:
        columns.append(table.get_column(settings.group).cast(pl.String).alias("group"))
    else:
        columns.append(pl.Series("group", ["Rows"] * table.height))
    if settings.value:
        columns.append(table.get_column(settings.value).cast(pl.Float64).alias("value"))
    frame = pl.DataFrame(columns)
    if settings.value:
        frame = frame.filter(pl.col("value").is_finite())
    category_codes, labels, other = _codes(frame, "category", settings.top)
    group_codes, groups, other_groups = _codes(frame, "group", 5)
    frame = frame.with_columns(category_codes.alias("c"), group_codes.alias("g"))
    representation = settings.representation
    if representation in (CategoryRepresentation.BOX, CategoryRepresentation.VIOLIN):
        assert settings.value is not None
        distributions = prepare_category_distributions(
            dataset, frame, labels, settings.value, settings.bandwidth, settings.seed
        )
        return CategoryChart(
            dataset.revision,
            settings,
            labels,
            (settings.value,),
            distributions.values,
            distributions.counts,
            (distributions.row_ids,),
            (distributions.first_positions,),
            frame.height,
            table.height,
            dataset.table.height,
            table.height - frame.height,
            other,
            0,
            distributions.series,
            distributions.scale,
        )
    magnitude = frame.get_column("value").abs().max() if settings.value else None
    scale = (
        float(magnitude) if isinstance(magnitude, (float, int)) and magnitude else 1.0
    )
    normalized = pl.col("value") / scale
    aggregation = (
        normalized.mean() * scale
        if representation == CategoryRepresentation.MEAN
        else normalized.median() * scale
        if representation == CategoryRepresentation.MEDIAN
        else normalized.sum() * scale
        if representation == CategoryRepresentation.SUM
        else pl.len().cast(pl.Float64)
    )
    aggregated = frame.group_by("g", "c").agg(
        aggregation.alias("aggregate"),
        pl.len().alias("count"),
        pl.col("row_id").head(SELECTION_LIMIT),
        pl.col("position").first(),
    )
    values = np.zeros((len(groups), len(labels)), dtype=np.float64)
    counts = np.zeros_like(values, dtype=np.int64)
    ids: list[list[tuple[int, ...]]] = [[() for _ in labels] for _ in groups]
    positions: list[list[int]] = [[0 for _ in labels] for _ in groups]
    for g, c, value, count, row_ids, position in aggregated.iter_rows():
        values[g, c], counts[g, c] = value, count
        ids[g][c], positions[g][c] = tuple(row_ids), position
    if not np.isfinite(values).all():
        raise ValueError(
            "Category aggregation overflowed; choose Mean or different values"
        )
    values.flags.writeable = counts.flags.writeable = False
    return CategoryChart(
        dataset.revision,
        settings,
        labels,
        groups,
        values,
        counts,
        tuple(tuple(row) for row in ids),
        tuple(tuple(row) for row in positions),
        frame.height,
        table.height,
        dataset.table.height,
        table.height - frame.height,
        other,
        other_groups,
    )
