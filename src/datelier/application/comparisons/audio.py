"""Explicit source-scoped audio comparisons with original unit families and links."""

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import replace

import numpy as np

from datelier.application.comparisons.base import ComparisonFamily, RecipeController
from datelier.application.comparisons.catalog import SourceCatalog
from datelier.application.comparisons.histograms import HistogramPlot, HistogramSeries
from datelier.application.sources.columns import record_mapping
from datelier.inspection.audio.collections import AudioCollectionSettings
from datelier.inspection.audio.comparisons import (
    AudioComparisonSettings,
    AudioComparisonSource,
    AudioComparisonViewSettings,
)
from datelier.inspection.audio.comparisons.jobs import AudioComparisonJobs
from datelier.inspection.audio.comparisons.types import (
    AudioComparisonCurve,
    AudioComparisonInput,
    AudioMetric,
    PreparedAudioComparison,
)


class AudioComparisonController(RecipeController[AudioComparisonSettings]):
    def __init__(
        self, catalog: SourceCatalog, focus: Callable[[str], None], executor: Executor
    ) -> None:
        super().__init__(AudioComparisonSettings())
        self.catalog, self.focus = catalog, focus
        self.jobs = AudioComparisonJobs(executor)
        self.view = AudioComparisonViewSettings()

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.AUDIO

    @property
    def active(self) -> PreparedAudioComparison | None:
        return self.jobs.active

    def validate(self, recipe: AudioComparisonSettings) -> None:
        recipe.validate()

    def mapping(self, identity: str) -> AudioComparisonSource | None:
        return next((s for s in self.draft.sources if s.file_id == identity), None)

    def map_files(self, identities: tuple[str, ...]) -> None:
        previous = {s.file_id: s for s in self.draft.sources}
        sources = []
        for identity in identities:
            choices = self.catalog.audio_choices(identity)
            preferred = next(
                (
                    c.name
                    for c in choices
                    if c.enabled and c.group in ("Audio", "Mapped Waveform")
                ),
                None,
            )
            column = preferred or next((c.name for c in choices if c.enabled), None)
            if identity in previous:
                sources.append(previous[identity])
            elif column:
                sources.append(
                    AudioComparisonSource(
                        identity,
                        AudioCollectionSettings(
                            column,
                            array_sample_rate=self.catalog.by_id[
                                identity
                            ].audio.array_sample_rate,
                            thresholds=self.catalog.by_id[identity].audio.thresholds,
                        ),
                    )
                )
        self.draft = replace(self.draft, sources=tuple(sources))

    def update_mapping(self, source: AudioComparisonSource) -> None:
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
                    AudioComparisonInput(
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

    @property
    def metrics(self) -> tuple[AudioMetric, ...]:
        return tuple(c.metric for c in self.active.curves) if self.active else ()

    @property
    def curve(self) -> AudioComparisonCurve | None:
        result = self.active
        if result is None:
            return None
        return next(
            (
                c
                for c in result.curves
                if (c.metric.name, c.metric.family, c.metric.channel)
                == (self.view.metric, self.view.family, self.view.channel)
            ),
            next(iter(result.curves), None),
        )

    @property
    def plot(self) -> HistogramPlot | None:
        result, curve = self.active, self.curve
        if result is None or curve is None:
            return None
        charts = curve.proportions if self.view.proportions else curve.counts
        series = tuple(
            HistogramSeries(p.file_id, label, curve.plot_x, values)
            for p, label, values in zip(
                result.profiles, result.labels, charts, strict=True
            )
            if values is not None
        )
        return HistogramPlot(
            ("Scaled " if curve.scaled else "") + curve.metric.label,
            "Proportion" if self.view.proportions else "Records",
            series,
            result.profiles[self.view.source].file_id,
            (id(result), curve.metric, self.view.proportions),
            f"Axis positions 0–1 represent original {curve.minimum}–{curve.maximum}."
            if curve.scaled
            else "",
        )

    @property
    def statistics(self) -> tuple[tuple[object, ...], ...]:
        result, curve = self.active, self.curve
        if result is None or curve is None:
            return ()
        return tuple(
            (label, curve.metric.label, s.values, s.minimum, s.maximum, s.mean)
            for label, s in zip(result.labels, curve.summaries, strict=True)
            if s is not None
        )

    def select_at(self, x: float) -> None:
        curve = self.curve
        if curve is None:
            return
        index = int(np.searchsorted(curve.edges, x, side="right") - 1)
        if x == curve.edges[-1]:
            index = len(curve.edges) - 2
        if 0 <= index < len(curve.edges) - 1:
            self.select(self.view.source, curve.metric, index)

    def select(self, source: int, metric: AudioMetric, bin_index: int) -> None:
        result = self.active
        if result is None or not 0 <= source < len(result.profiles):
            raise ValueError("Choose a current audio comparison source")
        identity = result.profiles[source].file_id
        file = self.catalog.by_id.get(identity)
        if file is None or file.dataset is None:
            raise ValueError("The contributing source closed or needs recovery")
        self.jobs.request_selection(result, source, metric, bin_index, file.dataset)
        self.focus(identity)

    def select_current(self) -> None:
        if self.curve:
            self.select(self.view.source, self.curve.metric, self.view.bin_index)

    def open_record(
        self, result: PreparedAudioComparison, source: int, row: int
    ) -> None:
        if result is not self.active or not 0 <= source < len(result.profiles):
            raise ValueError("The audio comparison changed")
        profile = result.profiles[source]
        if not 0 <= row < profile.records.height:
            raise ValueError("Choose a current audio record")
        record = profile.records.row(row, named=True)
        self.catalog.open_record(
            profile.file_id,
            profile.revision,
            int(record["position"]),
            int(record["row_id"]),
            profile.settings.column or "",
            profile.mapping is not None,
            profile.settings,
        )
        self.focus(profile.file_id)

    def abandon(self) -> None:
        self.jobs.clear()
        self.jobs.message = "Executing work is abandoned and cannot publish."

    def close(self) -> None:
        self.jobs.close()
