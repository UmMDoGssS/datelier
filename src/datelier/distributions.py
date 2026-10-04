"""Comparable numeric distributions; only bounded samples cross into NumPy."""

import math
from dataclasses import dataclass
from threading import Lock
from typing import cast

import numpy as np
import polars as pl
from numpy.typing import NDArray
from scipy.stats import gaussian_kde
from threadpoolctl import threadpool_limits

from datelier.dataset import Dataset
from datelier.plotting import numeric_columns
from datelier.sampling import seeded_sample

# BLAS thread limits are process-wide. Serialize these short density sections
# so overlapping obsolete/current preparation jobs cannot restore each other's
# limits midway through an evaluation.
_DENSITY_LOCK = Lock()


@dataclass(frozen=True)
class DistributionSettings:
    columns: tuple[str, ...] = ()
    standardize: bool = False
    density: bool = True
    bandwidth: float = 1.0
    seed: int = 42

    def validate(self) -> None:
        if len(self.columns) > 8 or len(set(self.columns)) != len(self.columns):
            raise ValueError("Choose at most eight distinct numeric profile columns")
        if not math.isfinite(self.bandwidth) or not 0.1 <= self.bandwidth <= 5:
            raise ValueError("KDE bandwidth multiplier must be 0.1–5")
        if not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("Seed must be UInt32")


@dataclass(frozen=True)
class NumericDistribution:
    name: str
    count: int
    sample_count: int
    histogram: NDArray[np.float64]
    ecdf_x: NDArray[np.float64]
    ecdf_y: NDArray[np.float64]
    kde_x: NDArray[np.float64]
    kde_y: NDArray[np.float64]
    box: tuple[float, float, float, float, float] | None
    outliers: NDArray[np.float64]
    note: str


@dataclass(frozen=True)
class Comparison:
    settings: DistributionSettings
    edges: NDArray[np.float64]
    series: tuple[NumericDistribution, ...]


def _scalar(value: object) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError("Expected a numeric statistic")
    return float(value)


def prepare_comparison(
    dataset: Dataset, settings: DistributionSettings, bins: int = 20
) -> Comparison:
    settings.validate()
    if not 1 <= bins <= 100:
        raise ValueError("Histogram bins must be 1–100")
    if any(name not in numeric_columns(dataset) for name in settings.columns):
        raise ValueError("Comparison requires existing numeric columns")
    values: list[pl.Series] = []
    notes: list[str] = []
    for name in settings.columns:
        raw = dataset.table.get_column(name).rename("value").cast(pl.Float64)
        finite = raw.filter(raw.is_finite())
        note = "Null and nonfinite values excluded."
        if settings.standardize and len(finite):
            scale = max(abs(_scalar(finite.min())), abs(_scalar(finite.max())))
            normalized = finite / scale if scale else finite
            deviation = _scalar(normalized.std(ddof=0))
            center = _scalar(normalized.mean())
            raw = (raw / scale if scale else raw) - center
            raw = raw / deviation if deviation else raw * 0
            note += " Z-score units." + (" Constant column." if not deviation else "")
        values.append(raw)
        notes.append(note)
    finite_values = [v.filter(v.is_finite()) for v in values]
    nonempty = [v for v in finite_values if len(v)]
    lo = min((_scalar(v.min()) for v in nonempty), default=0)
    hi = max((_scalar(v.max()) for v in nonempty), default=1)
    # Explicitly reject unrepresentable shared coordinates rather than publish
    # an empty histogram. The single-column profile retains its scaled fallback.
    if not math.isfinite(hi - lo):
        raise ValueError("Comparison range overflows; enable z-score scaling")
    if lo == hi:
        delta = max(0.5, abs(lo) * 1e-6)
        lo, hi = lo - delta, hi + delta
    edges = np.linspace(lo, hi, bins + 1)
    if not np.all(np.diff(edges) > 0):
        raise ValueError("Comparison bins lose precision; enable z-score scaling")
    distributions = []
    for name, raw, finite, note in zip(
        settings.columns, values, finite_values, notes, strict=True
    ):
        frame = pl.DataFrame({"value": raw, "id": dataset.row_ids}).filter(
            pl.col("value").is_finite()
        )
        sample = seeded_sample(frame, 2_000, settings.seed)["value"].to_numpy()
        sample = np.sort(sample)
        unique, counts = np.unique(sample, return_counts=True)
        ecdf = np.cumsum(counts).astype(np.float64) / max(1, len(sample))
        histogram = finite.hist(bins=edges.tolist())["count"].to_numpy().astype(float)
        # Explicit bins count one slot per interval in Polars, including the end.
        if histogram.sum() != len(finite):
            raise ValueError(f"Histogram did not account for all values in {name}")
        if settings.density and len(finite):
            histogram /= len(finite) * np.diff(edges)
        kde_x = np.linspace(lo, hi, 256)
        kde_y = np.array([], dtype=np.float64)
        if len(sample) >= 2 and np.ptp(sample) > 0:
            try:
                with _DENSITY_LOCK, threadpool_limits(limits=1, user_api="blas"):
                    estimator = gaussian_kde(sample)
                    estimator.set_bandwidth(estimator.factor * settings.bandwidth)
                    # SciPy's untyped return is isolated at the density boundary.
                    kde_y = cast(NDArray[np.float64], estimator(kde_x))
                if not np.isfinite(kde_y).all():
                    raise ValueError("Density is nonfinite")
            except ValueError, np.linalg.LinAlgError:
                note += " KDE unavailable for this sample."
        else:
            note += " KDE needs at least two distinct sample values."
        box = None
        outliers = np.array([], dtype=np.float64)
        if len(finite):
            q1, median, q3 = (
                _scalar(finite.quantile(q, interpolation="linear"))
                for q in (0.25, 0.5, 0.75)
            )
            iqr = q3 - q1
            inliers = finite.filter(
                (finite >= q1 - 1.5 * iqr) & (finite <= q3 + 1.5 * iqr)
            )
            box = (_scalar(inliers.min()), q1, median, q3, _scalar(inliers.max()))
            outliers = sample[(sample < box[0]) | (sample > box[4])][:150]
        if not len(kde_y):
            kde_x = np.array([], dtype=np.float64)
        for array in (histogram, unique, ecdf, kde_x, kde_y, outliers):
            array.flags.writeable = False
        distributions.append(
            NumericDistribution(
                name,
                len(finite),
                len(sample),
                histogram,
                unique,
                ecdf,
                kde_x,
                kde_y,
                box,
                outliers,
                note,
            )
        )
    edges.flags.writeable = False
    return Comparison(settings, edges, tuple(distributions))
