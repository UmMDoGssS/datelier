"""Scoped exact/sampled image comparisons, compatible curves and record commands."""

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import replace

import numpy as np

from datelier.application.comparisons.base import ComparisonFamily, RecipeController
from datelier.application.comparisons.catalog import SourceCatalog
from datelier.application.comparisons.histograms import HistogramPlot, HistogramSeries
from datelier.application.media.images import summary_row
from datelier.application.sources.columns import record_mapping
from datelier.inspection.images.comparisons.jobs import ImageComparisonJobs
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
    ImageComparisonViewSettings,
)
from datelier.inspection.images.comparisons.types import (
    ImageComparisonCurve,
    ImageComparisonInput,
    PreparedImageComparison,
)
from datelier.inspection.images.profiles import ImageProfileSettings


class ImageComparisonController(RecipeController[ImageComparisonSettings]):
    def __init__(
        self, catalog: SourceCatalog, focus: Callable[[str], None], executor: Executor
    ) -> None:
        super().__init__(ImageComparisonSettings())
        self.catalog, self.focus = catalog, focus
        self.jobs = ImageComparisonJobs(executor)
        self.view = ImageComparisonViewSettings()
        self.statistics: tuple[tuple[object, ...], ...] = ()
        self._prepared: PreparedImageComparison | None = None

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.IMAGES

    @property
    def active(self) -> PreparedImageComparison | None:
        return self.jobs.active

    def validate(self, recipe: ImageComparisonSettings) -> None:
        recipe.validate()

    def mapping(self, identity: str) -> ImageComparisonSource | None:
        return next((s for s in self.draft.sources if s.file_id == identity), None)

    def map_files(self, identities: tuple[str, ...]) -> None:
        previous = {s.file_id: s for s in self.draft.sources}
        sources = []
        for identity in identities:
            choices = self.catalog.image_choices(identity)
            preferred = next(
                (
                    c.name
                    for c in choices
                    if c.enabled and c.group in ("Image", "Mapped Image / grayscale")
                ),
                None,
            )
            column = preferred or next((c.name for c in choices if c.enabled), None)
            if identity in previous:
                sources.append(previous[identity])
            elif column:
                sources.append(
                    ImageComparisonSource(identity, ImageProfileSettings(column))
                )
        self.draft = replace(self.draft, sources=tuple(sources))

    def update_mapping(self, source: ImageComparisonSource) -> None:
        self.draft = replace(
            self.draft,
            sources=tuple(
                source if s.file_id == source.file_id else s for s in self.draft.sources
            ),
        )

    def prune(self, identities: set[str]) -> None:
        self.recipes = tuple(
            replace(r, sources=tuple(s for s in r.sources if s.file_id in identities))
            for r in self.recipes
        )
        self.draft = replace(
            self.draft,
            sources=tuple(s for s in self.draft.sources if s.file_id in identities),
        )

    def _bind(self) -> None:
        inputs = []
        for mapping in self.recipe.sources if self.recipe else ():
            source = self.catalog.by_id.get(mapping.file_id)
            if source and source.inspection:
                active = source.inspection
                inputs.append(
                    ImageComparisonInput(
                        mapping,
                        active.dataset,
                        source.title,
                        source.view_name,
                        source.references,
                        source.index,
                        source.selection,
                        source.arrays,
                        active.imported.array_catalog,
                        record_mapping(active, mapping.profile.column),
                    )
                )
        self.jobs.bind(self.recipe, tuple(inputs))

    def prepare(self) -> None:
        self.apply()
        self._bind()
        self.jobs.request()

    def sync(self) -> None:
        self._bind()
        self.jobs.poll()
        self.message = self.jobs.message
        selection = self.jobs.poll_selection(self.catalog.datasets)
        if selection:
            self.catalog.apply_selection(selection)
        result = self.active
        if result:
            self.view = replace(
                self.view,
                source=min(self.view.source, len(result.profiles) - 1),
                bin_index=min(self.view.bin_index, result.settings.bins - 1),
            )
        if result is self._prepared:
            return
        self._prepared = result
        self.statistics = (
            tuple(
                (label, *summary_row(s))
                for label, p in zip(result.labels, result.profiles, strict=True)
                for s in (*p.dimension_summaries, *p.summaries)
            )
            if result
            else ()
        )

    @property
    def color_groups(self) -> tuple[tuple[str, str], ...]:
        return (
            tuple(
                dict.fromkeys(
                    (c.key.mode, c.key.dtype)
                    for c in self.active.curves
                    if c.key.mode != "Dimensions"
                )
            )
            if self.active
            else ()
        )

    @property
    def channels(self) -> tuple[str, ...]:
        group = (self.view.mode, self.view.dtype)
        if group not in self.color_groups:
            group = next(iter(self.color_groups), None)
        return (
            tuple(
                c.key.name
                for c in self.active.curves
                if (c.key.mode, c.key.dtype) == group
            )
            if self.active
            else ()
        )

    @property
    def curve(self) -> ImageComparisonCurve | None:
        result = self.active
        if result is None:
            return None
        if self.view.tab == "Dimensions":
            return next(
                (
                    c
                    for c in result.curves
                    if c.key.mode == "Dimensions" and c.key.name == self.view.dimension
                ),
                None,
            )
        group = (self.view.mode, self.view.dtype)
        if group not in self.color_groups:
            group = next(iter(self.color_groups), None)
        channel = (
            self.view.channel
            if self.view.channel in self.channels
            else next(iter(self.channels), None)
        )
        return next(
            (
                c
                for c in result.curves
                if (c.key.mode, c.key.dtype) == group and c.key.name == channel
            ),
            None,
        )

    @property
    def plot(self) -> HistogramPlot | None:
        result, curve = self.active, self.curve
        if result is None or curve is None:
            return None
        charts = curve.proportions if self.view.proportions else curve.counts
        normalized = any(c.scaled for c in charts if c is not None)
        series = []
        for i, chart in enumerate(charts):
            if chart is None or chart.plot_counts is None:
                continue
            x = chart.normalized_plot_x if normalized else chart.plot_x
            if x is not None:
                series.append(
                    HistogramSeries(
                        result.profiles[i].file_id,
                        result.labels[i],
                        x,
                        chart.plot_counts,
                    )
                )
        return HistogramPlot(
            ("Scaled " if normalized else "") + curve.key.label,
            "Proportion"
            if self.view.proportions
            else "Images"
            if curve.key.mode == "Dimensions"
            else "Profiled pixel values",
            tuple(series),
            result.profiles[self.view.source].file_id,
            (id(result), curve.key, self.view.proportions),
            "Axis positions are 0–1; exact original bounds are in Statistics."
            if normalized
            else "",
        )

    def select_at(self, x: float) -> None:
        curve = self.curve
        if curve is None or curve.key.mode != "Dimensions":
            return
        chart = next((c for c in curve.counts if c is not None), None)
        if chart is None:
            return
        normalized = any(c.scaled for c in curve.counts if c is not None)
        index = (
            int(np.floor(x * self.active.settings.bins))
            if normalized and self.active
            else int(np.searchsorted(chart.edges, x, side="right") - 1)
        )
        maximum = 1 if normalized else chart.edges[-1]
        if x == maximum:
            index = len(chart.counts) - 1
        if 0 <= index < len(chart.counts):
            self.select(self.view.source, self.view.dimension, index)

    def select(self, source: int, dimension: str, bin_index: int) -> None:
        result = self.active
        if result is None or not 0 <= source < len(result.profiles):
            raise ValueError("Choose a current image comparison source")
        identity = result.profiles[source].file_id
        file = self.catalog.by_id.get(identity)
        if file is None or file.dataset is None:
            raise ValueError("The contributing source closed or needs recovery")
        self.jobs.request_selection(result, source, dimension, bin_index, file.dataset)
        self.focus(identity)

    def open_record(
        self, result: PreparedImageComparison, source: int, row: int
    ) -> None:
        if result is not self.active or not 0 <= source < len(result.profiles):
            raise ValueError("The image comparison changed")
        profile = result.profiles[source]
        if not 0 <= row < profile.records.height:
            raise ValueError("Choose a current image record")
        record = profile.records.row(row, named=True)
        self.catalog.open_record(
            profile.file_id,
            profile.revision,
            int(record["position"]),
            int(record["row_id"]),
            profile.settings.column or "",
            profile.mapping is not None,
        )
        self.focus(profile.file_id)

    def abandon(self) -> None:
        self.jobs.clear()
        self.jobs.message = "Executing work is abandoned and cannot publish."

    def close(self) -> None:
        self.jobs.close()
        self._prepared = None
        self.statistics = ()
