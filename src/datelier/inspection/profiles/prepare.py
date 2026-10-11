"""Type-aware, bounded inspection profiles prepared outside GUI callbacks."""

import math
from dataclasses import dataclass, replace
from enum import StrEnum

import polars as pl

from datelier.core import Dataset, DatasetRevision
from datelier.core.column_roles import (
    LIST_ROLES,
    PLOTTABLE_ROLES,
    ColumnRole,
    list_element_role,
)
from datelier.inspection.profiles.lists import ListStatistics, prepare_list
from datelier.inspection.profiles.numeric import (
    NumericStatistics,
    prepare_numeric_statistics,
)

MAX_PROFILE_COLUMNS = 128
COUNT_ROW_LIMIT = 100_000


class ProfileKind(StrEnum):
    NUMERIC = "Numeric"
    CATEGORICAL = "Categorical"
    TEMPORAL = "Temporal"
    UNSUPPORTED = "Unsupported"
    TEXT = "Text"
    IDENTIFIER = "Identifier"
    PATH = "Local path"
    IMAGE = "Image"
    AUDIO = "Audio"
    EXTERNAL_TEXT = "External text"
    LIST = "List"
    OBJECT = "Object"


@dataclass(frozen=True)
class Distribution:
    labels: tuple[str, ...]
    counts: tuple[int, ...]
    edges: tuple[float, ...] = ()
    tick_labels: tuple[str, ...] = ()


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
    histogram_scale: float = 1.0
    statistics: NumericStatistics | None = None
    nonnull_count: int = 0
    unique_count: int | None = None
    list_statistics: ListStatistics | None = None


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


def _temporal_range(series: pl.Series) -> tuple[str, str]:
    extrema = (
        series.rename("value")
        .to_frame()
        .select(
            pl.col("value").min().alias("minimum"),
            pl.col("value").max().alias("maximum"),
        )
    )
    if isinstance(series.dtype, pl.Duration):
        extrema = extrema.cast(pl.Int64).cast(pl.String)
        minimum, maximum = extrema.row(0)
        unit = series.dtype.time_unit
        return f"{minimum} {unit}", f"{maximum} {unit}"
    if series.dtype == pl.Time:
        extrema = extrema.select(pl.all().dt.to_string("%H:%M:%S%.9f"))
    else:
        extrema = extrema.cast(pl.String)
    minimum, maximum = extrema.row(0)
    return str(minimum), str(maximum)


def prepare_range_profile(
    series: pl.Series, kind: ProfileKind, bins: int
) -> ColumnProfile:
    origin: int | None = None
    if kind == ProfileKind.TEMPORAL:
        physical = series.rename("value").to_physical()
        physical_min = physical.min()
        origin = physical_min if isinstance(physical_min, int) else None
        # Shift in integer space before Float64 conversion so close timestamps
        # keep nanosecond differences. Int128 avoids overflow across Int64 dates.
        values = (
            physical.to_frame()
            .select(
                (
                    pl.col("value").cast(pl.Int128) - pl.lit(origin, dtype=pl.Int128)
                ).cast(pl.Float64)
            )
            .to_series()
            if isinstance(origin, int)
            else physical.cast(pl.Float64)
        )
    else:
        values = series.rename("value").cast(pl.Float64)
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
    minimum_value, maximum_value = finite.min(), finite.max()
    assert isinstance(minimum_value, (int, float))
    assert isinstance(maximum_value, (int, float))
    scale = max(abs(minimum_value), abs(maximum_value))
    # A finite column can still overflow its range or sum. Normalize extreme
    # ranges before histogramming, and compute its mean without overflowing.
    scaled_histogram = not math.isfinite(maximum_value - minimum_value)
    histogram_values = finite / scale if scaled_histogram else finite
    hist_min, hist_max = histogram_values.min(), histogram_values.max()
    assert isinstance(hist_min, (int, float)) and isinstance(hist_max, (int, float))
    if hist_min == hist_max:
        # A fixed 0.5 margin vanishes at large magnitudes. Use a representable
        # interval around constants so the plot never has zero-width bins.
        margin = max(0.5, abs(hist_min) * 1e-6)
        lower, upper = hist_min - margin, hist_max + margin
        if not math.isfinite(lower) or not math.isfinite(upper):
            histogram_values = finite / scale
            scaled_histogram = True
            lower, upper = float(hist_min / scale) - 0.5, float(hist_max / scale) + 0.5
    else:
        lower, upper = float(hist_min), float(hist_max)
    # Remove boundaries lost to Float64 precision rather than draw zero-width
    # bars or imply that more distinct intervals exist than can be represented.
    edges = tuple(
        dict.fromkeys(
            edge
            for i in range(bins)
            if (edge := lower + (upper - lower) * i / bins) < upper
        )
    ) + (upper,)
    hist = histogram_values.hist(bins=list(edges))
    if sum(hist.get_column("count")) != count:
        raise ValueError(f"Could not account for all finite values in {series.name!r}")
    # Polars supplies explicit interval labels, including its boundary policy.
    labels = tuple(str(value) for value in hist.get_column("category").to_list())
    if kind == ProfileKind.TEMPORAL:
        minimum, maximum = _temporal_range(series)
        note = (
            f"Bins use {series.dtype} physical units relative to the minimum; "
            "the range preserves temporal precision."
        )
    else:
        minimum, maximum = str(finite.min()), str(finite.max())
        note = "Exact finite-value distribution; null and nonfinite values excluded."
    if scaled_histogram:
        note += (
            f" Histogram labels use values divided by {scale:.6g} to avoid overflow."
        )
    mean = (
        ((finite / scale).mean() if scale else 0.0)
        if kind == ProfileKind.NUMERIC
        else None
    )
    if isinstance(mean, (int, float)):
        mean = max(-1.0, min(1.0, mean)) * scale
    tick_labels: tuple[str, ...] = ()
    if kind == ProfileKind.TEMPORAL and isinstance(origin, int):
        ticks = pl.Series([origin + round(edge) for edge in edges], dtype=pl.Int128)
        ticks = ticks.cast(series.dtype)
        if isinstance(series.dtype, pl.Duration):
            tick_labels = tuple(
                f"{value} {series.dtype.time_unit}" for value in ticks.cast(pl.Int64)
            )
        elif series.dtype == pl.Time:
            tick_labels = tuple(ticks.dt.to_string("%H:%M:%S%.9f").to_list())
        else:
            tick_labels = tuple(ticks.cast(pl.String).to_list())
    return ColumnProfile(
        series.name,
        str(series.dtype),
        kind,
        series.null_count(),
        invalid,
        minimum,
        maximum,
        float(mean) if isinstance(mean, (int, float)) and math.isfinite(mean) else None,
        Distribution(
            labels, tuple(hist.get_column("count").to_list()), edges, tick_labels
        ),
        count,
        note=note,
        histogram_scale=scale if scaled_histogram else 1.0,
    )


def _counts_profile(
    series: pl.Series, top: int, *, unit: str = "rows"
) -> ColumnProfile:
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
            f"Counts from first {COUNT_ROW_LIMIT:,} {unit} (sample). "
            if sampled
            else "Exact counts. "
        )
        + f"Top {top}; remaining values grouped as Other; nulls excluded. "
        + "Category labels truncate after 120 characters.",
    )


def prepare_profiles(
    dataset: Dataset,
    *,
    column_limit: int = 32,
    bins: int = 20,
    top: int = 12,
    column: str | None = None,
    columns: tuple[str, ...] | None = None,
) -> Profiles:
    if (
        not 1 <= column_limit <= MAX_PROFILE_COLUMNS
        or not 1 <= bins <= 100
        or not 1 <= top <= 100
    ):
        raise ValueError("Profile limits: 1–128 columns, 1–100 bins/counts")
    table = dataset.table
    if columns is not None and (
        column is not None or len(set(columns)) != len(columns)
    ):
        raise ValueError("Choose distinct profile columns or a single focus")
    profiles = []
    series_list = (
        (table.get_column(name) for name in columns)
        if columns is not None
        else (table.get_column(column),)
        if column is not None
        else (
            table.get_column(info.name)
            for info in (dataset.roles or ())
            if info.role
            in (
                *PLOTTABLE_ROLES,
                *LIST_ROLES,
                ColumnRole.OBJECT,
                ColumnRole.UNSUPPORTED,
            )
        )
    )
    for index, series in enumerate(series_list):
        if columns is None and index >= column_limit:
            break
        info = dataset.role(series.name)
        kind = ProfileKind(list_element_role(info.role, series.dtype).value)
        list_stats = None
        physical = str(series.dtype)
        if info.role in LIST_ROLES:
            series, list_stats = prepare_list(series)
        distinct = (
            series.n_unique() - int(series.null_count() > 0)
            if list_stats is not None
            and kind
            in (ProfileKind.NUMERIC, ProfileKind.CATEGORICAL, ProfileKind.TEMPORAL)
            else info.distinct
        )
        if kind in (ProfileKind.NUMERIC, ProfileKind.TEMPORAL):
            profile = prepare_range_profile(series, kind, bins)
        elif kind == ProfileKind.CATEGORICAL:
            profile = _counts_profile(
                series, top, unit="elements" if list_stats else "rows"
            )
        else:
            profile = ColumnProfile(
                series.name,
                str(series.dtype),
                kind,
                series.null_count(),
                distinct_count=info.distinct,
                note=(
                    f"{kind} excluded from analysis. "
                    "Change its role in Schema to include it."
                    if info.role
                    not in (*PLOTTABLE_ROLES, *LIST_ROLES, ColumnRole.OBJECT)
                    else "Text elements; calculate a corpus profile with text tools."
                    if kind == ProfileKind.TEXT
                    else "Identifier elements are excluded from scalar analysis; "
                    "choose a compatible list interpretation in Schema to analyze them."
                    if kind == ProfileKind.IDENTIFIER
                    else "Object values have no scalar plot; choose the column "
                    "as the primary field in Inspect to read its complete value."
                    if kind == ProfileKind.OBJECT or isinstance(series.dtype, pl.Struct)
                    else "No scalar element values to plot."
                ),
            )
        profiles.append(
            replace(
                profile,
                dtype=physical,
                statistics=prepare_numeric_statistics(series, uniques=distinct)
                if kind == ProfileKind.NUMERIC
                else None,
                nonnull_count=len(series) - series.null_count()
                if list_stats
                else info.nonnull,
                unique_count=distinct,
                list_statistics=list_stats,
                note=(
                    "Flattened leaf elements across all rows; null/empty containers "
                    "contribute no elements. " + profile.note
                    if list_stats
                    else profile.note
                ),
            )
        )
    return Profiles(dataset.revision, table.height, table.width, tuple(profiles))
