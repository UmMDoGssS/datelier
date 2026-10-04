"""Type-aware, bounded inspection profiles prepared outside GUI callbacks."""

import math
from dataclasses import dataclass
from enum import StrEnum

import polars as pl

from datelier.dataset import Dataset, DatasetRevision

MAX_PROFILE_COLUMNS = 128
COUNT_ROW_LIMIT = 100_000


class ProfileKind(StrEnum):
    NUMERIC = "Numeric"
    CATEGORICAL = "Categorical"
    TEMPORAL = "Temporal"
    UNSUPPORTED = "Unsupported"


@dataclass(frozen=True)
class Distribution:
    labels: tuple[str, ...]
    counts: tuple[int, ...]


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    dtype: str
    kind: ProfileKind
    null_count: int
    nonfinite_count: int = 0
    minimum: str = ""
    maximum: str = ""
    mean: float | None = None
    distribution: Distribution = Distribution((), ())
    counted_rows: int = 0
    distinct_count: int | None = None
    other_count: int = 0
    note: str = ""


@dataclass(frozen=True)
class Profiles:
    revision: DatasetRevision
    row_count: int
    total_columns: int
    columns: tuple[ColumnProfile, ...]


def profile_kind(dtype: pl.DataType) -> ProfileKind:
    if dtype.is_numeric():
        return ProfileKind.NUMERIC
    if dtype.is_temporal():
        return ProfileKind.TEMPORAL
    if dtype in (pl.String, pl.Boolean, pl.Categorical) or isinstance(dtype, pl.Enum):
        return ProfileKind.CATEGORICAL
    return ProfileKind.UNSUPPORTED


def _range_profile(series: pl.Series, kind: ProfileKind, bins: int) -> ColumnProfile:
    values = (
        series.cast(pl.Float64)
        if kind == ProfileKind.NUMERIC
        else series.to_physical().cast(pl.Float64)
    )
    values = values.rename("value")
    finite = values.filter(values.is_finite())
    count = len(finite)
    invalid = len(series) - series.null_count() - count
    if not count:
        return ColumnProfile(
            series.name,
            str(series.dtype),
            kind,
            series.null_count(),
            invalid,
            note="No finite values to plot.",
        )
    hist = finite.hist(bin_count=bins)
    # Polars supplies explicit interval labels, including its boundary policy.
    labels = tuple(str(value) for value in hist.get_column("category").to_list())
    if kind == ProfileKind.TEMPORAL:
        valid = series.rename("value").drop_nulls()
        minimum, maximum = str(valid.min()), str(valid.max())
        note = (
            f"Bins use {series.dtype} physical units; "
            "range is shown as temporal values."
        )
    else:
        minimum, maximum = str(finite.min()), str(finite.max())
        note = "Exact finite-value distribution; null and nonfinite values excluded."
    mean = finite.mean() if kind == ProfileKind.NUMERIC else None
    return ColumnProfile(
        series.name,
        str(series.dtype),
        kind,
        series.null_count(),
        invalid,
        minimum,
        maximum,
        float(mean) if isinstance(mean, (int, float)) and math.isfinite(mean) else None,
        Distribution(labels, tuple(hist.get_column("count").to_list())),
        count,
        note=note,
    )


def _counts_profile(series: pl.Series, top: int) -> ColumnProfile:
    sample = series.head(COUNT_ROW_LIMIT).drop_nulls().rename("value")
    counts = sample.value_counts(sort=True)
    # Tie ordering is deterministic without relying on hash/group order.
    counts = counts.sort(["count", "value"], descending=[True, False])
    visible = counts.head(top)
    sizes = tuple(visible.get_column("count").to_list())
    sampled = len(series) > COUNT_ROW_LIMIT
    return ColumnProfile(
        series.name,
        str(series.dtype),
        ProfileKind.CATEGORICAL,
        series.null_count(),
        distribution=Distribution(
            tuple(str(v)[:120] for v in visible.get_column("value").to_list()),
            sizes,
        ),
        counted_rows=len(sample),
        distinct_count=counts.height,
        other_count=len(sample) - sum(sizes),
        note=(
            f"Counts from first {COUNT_ROW_LIMIT:,} rows (sample). "
            if sampled
            else "Exact counts. "
        )
        + f"Top {top}; remaining values grouped as Other; nulls excluded.",
    )


def prepare_profiles(
    dataset: Dataset,
    *,
    column_limit: int = 32,
    bins: int = 20,
    top: int = 12,
    column: str | None = None,
) -> Profiles:
    if (
        not 1 <= column_limit <= MAX_PROFILE_COLUMNS
        or not 1 <= bins <= 100
        or not 1 <= top <= 100
    ):
        raise ValueError("Profile limits: 1–128 columns, 1–100 bins/counts")
    table = dataset.table
    profiles = []
    series_list = (
        (table.get_column(column),) if column is not None else table[:, :column_limit]
    )
    for series in series_list:
        kind = profile_kind(series.dtype)
        if kind in (ProfileKind.NUMERIC, ProfileKind.TEMPORAL):
            profile = _range_profile(series, kind, bins)
        elif kind == ProfileKind.CATEGORICAL:
            profile = _counts_profile(series, top)
        else:
            profile = ColumnProfile(
                series.name,
                str(series.dtype),
                kind,
                series.null_count(),
                note="This type has no automatic plot.",
            )
        profiles.append(profile)
    return Profiles(dataset.revision, table.height, table.width, tuple(profiles))
