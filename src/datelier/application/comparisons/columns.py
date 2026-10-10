"""Column comparison preparation and original-row links outside native rendering."""

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from datelier.application.comparisons.base import ComparisonFamily, RecipeController
from datelier.application.comparisons.catalog import SourceCatalog
from datelier.core.column_roles import ColumnRole
from datelier.inspection.comparison_settings import ComparisonSettings, ComparisonSource
from datelier.inspection.comparisons.jobs import ComparisonJobs
from datelier.inspection.comparisons.types import PreparedComparison


@dataclass(frozen=True)
class ColumnSeries:
    identity: str
    label: str
    color: tuple[float, float, float, float] | None
    x: NDArray[np.float64]
    y: NDArray[np.float64]


class ColumnComparisonController(RecipeController[ComparisonSettings]):
    def __init__(
        self, catalog: SourceCatalog, focus: Callable[[str], None], executor: Executor
    ) -> None:
        super().__init__(ComparisonSettings())
        self.catalog, self.focus = catalog, focus
        self.jobs = ComparisonJobs(executor=executor)
        self.selected_source = self.selected_bin = 0
        self.height = 260.0
        self.series: tuple[ColumnSeries, ...] = ()
        self.statistics: tuple[tuple[object, ...], ...] = ()
        self._prepared: PreparedComparison | None = None

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.COLUMNS

    @property
    def active(self) -> PreparedComparison | None:
        return (
            self.jobs.states[self.index].result
            if self.index < len(self.jobs.states)
            else None
        )

    def validate(self, recipe: ComparisonSettings) -> None:
        recipe.validate()

    def map_files(self, identities: tuple[str, ...]) -> None:
        previous = {s.file_id: s for s in self.draft.sources}
        sources = []
        for identity in identities:
            existing = previous.get(identity)
            choices = self.catalog.column_choices(identity)
            column = next((c.name for c in choices if c.enabled), None)
            if existing:
                sources.append(existing)
            elif column:
                sources.append(ComparisonSource(identity, column))
        self.draft = replace(self.draft, sources=tuple(sources))

    def mapping(self, identity: str) -> ComparisonSource | None:
        return next((s for s in self.draft.sources if s.file_id == identity), None)

    def update_mapping(self, source: ComparisonSource) -> None:
        self.draft = replace(
            self.draft,
            sources=tuple(
                source if s.file_id == source.file_id else s for s in self.draft.sources
            ),
        )

    def prune(self, identities: set[str]) -> None:
        self.recipes = tuple(
            replace(
                recipe,
                sources=tuple(s for s in recipe.sources if s.file_id in identities),
            )
            for recipe in self.recipes
        )
        self.draft = replace(
            self.draft,
            sources=tuple(s for s in self.draft.sources if s.file_id in identities),
        )

    def sync(self) -> None:
        self.prune(set(self.catalog.by_id))
        self.jobs.sync(
            self.recipes,
            self.catalog.datasets,
            {f.identity: f.title for f in self.catalog.files},
            {f.identity: f.view_name for f in self.catalog.files},
        )
        self.message = (
            self.jobs.states[self.index].message
            if self.jobs.states
            else "Map at least two columns and apply the comparison."
        )
        selection = self.jobs.poll_selection(self.catalog.datasets)
        if selection:
            self.catalog.apply_selection(selection)
        prepared = self.active
        if prepared:
            self.selected_source = min(self.selected_source, len(prepared.series) - 1)
            self.selected_bin = min(
                self.selected_bin,
                max(0, len(prepared.series[self.selected_source].counts) - 1),
            )
        if prepared is self._prepared:
            return
        self._prepared = prepared
        self.series = ()
        self.statistics = ()
        if prepared:
            width = 0.8 / len(prepared.series)
            self.series = tuple(
                ColumnSeries(
                    s.origin.file_id,
                    f"{s.label} / {s.origin.column}",
                    s.color,
                    np.repeat(np.asarray(prepared.edges), 2)
                    if prepared.kind == ColumnRole.NUMERIC
                    else s.heights,
                    np.concatenate(([0], np.repeat(s.heights, 2), [0]))
                    if prepared.kind == ColumnRole.NUMERIC
                    else np.arange(len(prepared.labels), dtype=np.float64)
                    - 0.4
                    + width * (index + 0.5),
                )
                for index, s in enumerate(prepared.series)
            )
            self.statistics = tuple(
                (
                    s.label,
                    s.origin.column,
                    s.rows,
                    s.included,
                    s.nulls,
                    s.nonfinite,
                    s.distinct,
                    s.statistics.minimum if s.statistics else None,
                    s.statistics.maximum if s.statistics else None,
                    s.statistics.mean if s.statistics else None,
                    s.statistics.std if s.statistics else None,
                    s.statistics.q25 if s.statistics else None,
                    s.statistics.median if s.statistics else None,
                    s.statistics.q75 if s.statistics else None,
                    s.statistics.mode if s.statistics else s.mode,
                    s.statistics.mode_count if s.statistics else s.mode_count,
                )
                for s in prepared.series
            )

    def select(self, series: int, bin_index: int) -> None:
        result = self.active
        if result is None or not 0 <= series < len(result.series):
            raise ValueError("Choose a current comparison series")
        if not 0 <= bin_index < len(result.series[series].counts):
            raise ValueError("Choose a displayed comparison bin or category")
        origin = result.series[series].origin
        source = self.catalog.by_id.get(origin.file_id)
        if source is None or source.dataset is None:
            raise ValueError("The contributing source closed or needs recovery")
        self.jobs.request_selection(result, series, bin_index, source.dataset)
        self.focus(origin.file_id)

    def close(self) -> None:
        self.jobs.close()
        self.series = self.statistics = ()
        self._prepared = None
