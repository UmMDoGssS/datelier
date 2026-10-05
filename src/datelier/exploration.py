"""Automatic dashboard preparation and revision-aware background publication."""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

from datelier.analysis_types import ClusteringResult
from datelier.category_charts import (
    CategoryChart,
    CategorySettings,
    prepare_category_chart,
)
from datelier.core.dataset import Dataset, DatasetRevision
from datelier.distribution_preview import DistributionPreview
from datelier.distributions import Comparison, DistributionSettings, prepare_comparison
from datelier.plotting import (
    Bars,
    Correlation,
    Scatter,
    feature_columns,
    prepare_bars,
    prepare_correlations,
    prepare_scatter,
)
from datelier.profile_preview import ProfilePreview
from datelier.profiling import Profiles, prepare_profiles
from datelier.relationships import Relationships, prepare_relationships


@dataclass(frozen=True)
class PlotSettings:
    profile_columns: int = 32
    bins: int = 20
    top_counts: int = 12
    correlation_columns: int = 8
    point_limit: int = 2_000
    scatter_pair: tuple[str, str] | None = None
    profile_column: str | None = None
    comparison: DistributionSettings = DistributionSettings()
    color_column: str | None = None
    relationship_features: tuple[str, ...] = ()
    clusters: ClusteringResult | None = field(default=None, compare=False, repr=False)
    scatter_z: str | None = None
    category_chart: CategorySettings | None = None
    diagonal_mode: int = 0

    def validate(self) -> None:
        self.comparison.validate()
        if self.category_chart is not None:
            self.category_chart.validate()
        if not (
            1 <= self.profile_columns <= 128
            and 1 <= self.bins <= 100
            and 1 <= self.top_counts <= 100
            and 2 <= self.correlation_columns <= 16
            and 1 <= self.point_limit <= 10_000
            and 0 <= self.diagonal_mode < 5
        ):
            raise ValueError("Plot settings exceed the displayed resource limits")


DEFAULT_SETTINGS = PlotSettings()


@dataclass(frozen=True)
class Dashboard:
    revision: DatasetRevision
    settings: PlotSettings
    profiles: Profiles
    correlations: tuple[Correlation, ...]
    scatters: tuple[Scatter, ...]
    bars: tuple[Bars, ...]
    comparison: Comparison | None = None
    relationships: Relationships | None = None
    category_chart: CategoryChart | None = None


def prepare_dashboard(
    dataset: Dataset, settings: PlotSettings = DEFAULT_SETTINGS
) -> Dashboard:
    settings.validate()
    profiles = prepare_profiles(
        dataset,
        column_limit=settings.profile_columns,
        bins=settings.bins,
        top=settings.top_counts,
        column=settings.profile_column,
    )
    correlations = prepare_correlations(
        dataset,
        column_limit=settings.correlation_columns,
        features=settings.relationship_features,
    )
    ranked = sorted(
        (c for c in correlations if c.value is not None),
        key=lambda c: -abs(c.value if c.value is not None else 0),
    )
    pairs = [(c.x_name, c.y_name) for c in ranked[:3]]
    if settings.scatter_pair is not None:
        pairs = [
            settings.scatter_pair,
            *[p for p in pairs if p != settings.scatter_pair],
        ][:3]
    if settings.scatter_z is not None:
        pairs = [p for p in pairs if settings.scatter_z not in p]
    scatters = tuple(
        prepare_scatter(
            dataset,
            *pair,
            limit=settings.point_limit,
            color=settings.color_column,
            clusters=settings.clusters,
            z=settings.scatter_z,
        )
        for pair in pairs
    )
    return Dashboard(
        dataset.revision,
        settings,
        profiles,
        correlations,
        scatters,
        tuple(prepare_bars(profile) for profile in profiles.columns),
        prepare_comparison(dataset, settings.comparison, settings.bins)
        if settings.comparison.columns
        else None,
        prepare_relationships(
            dataset,
            settings.relationship_features
            or feature_columns(dataset)[: settings.correlation_columns],
            correlations,
            settings.bins,
            settings.diagonal_mode,
            settings.comparison.bandwidth,
            settings.comparison.seed,
        ),
        prepare_category_chart(dataset, settings.category_chart)
        if settings.category_chart is not None
        else None,
    )


class Explorer:
    def __init__(self) -> None:
        self.distribution = DistributionPreview()
        self.profiles = ProfilePreview()
        self.active: Dashboard | None = None
        self.message = "Open a dataset for automatic exploration."
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="explore")
        self._future: Future[Dashboard] | None = None
        self._revision: DatasetRevision | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def request(
        self, dataset: Dataset, settings: PlotSettings = DEFAULT_SETTINGS
    ) -> None:
        if self._closed:
            raise ValueError("Explorer is closed")
        settings.validate()
        self.abandon()
        self._revision = dataset.revision
        self._future = self._executor.submit(prepare_dashboard, dataset, settings)
        self.message = "Preparing profiles and plots…"

    def poll(self, revision: DatasetRevision | None) -> bool:
        self.distribution.poll(revision)
        self.profiles.poll(revision)
        if self.active is not None and self.active.revision != revision:
            self.active = None
        future = self._future
        if future is None or not future.done():
            return False
        self._future = None
        if revision != self._revision:
            self.message = "Dataset changed; obsolete plots ignored."
            return False
        try:
            result = future.result()
        except Exception as error:
            self.message = f"Exploration failed: {error}"
            return False
        self.active = result
        self.message = "Profiles and plots ready."
        return True

    def abandon(self) -> None:
        self.distribution.clear()
        self.profiles.clear()
        if self._future is not None:
            self._future.cancel()
            self._future = None
        self.active = None
        self.message = "Exploration abandoned; an executing job may still finish."

    def close(self) -> None:
        self.distribution.close()
        self.profiles.close()
        self.abandon()
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
