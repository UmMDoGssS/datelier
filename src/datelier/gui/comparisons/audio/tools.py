"""Audio contributors share selectors, scopes, recipes and linked-row commands."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.comparisons import ComparisonFamily
from datelier.application.comparisons.audio import AudioComparisonController
from datelier.application.tabular import SingleSelection
from datelier.gui.comparisons.base import ComparisonTools
from datelier.gui.comparisons.controls import (
    ContributorControls,
    RecipeControls,
    RowLinkControls,
    SourceCaption,
)
from datelier.gui.components.actions import JobSnapshot
from datelier.gui.components.inputs import ChoiceField, ColumnPicker, StateFields
from datelier.gui.components.layout import Container, FrameContext
from datelier.gui.context.audio import AudioSamplingFields
from datelier.inspection.audio.comparisons import AudioComparisonSource
from datelier.inspection.audio.comparisons.types import AudioMetric


class AudioSourceForm(Container):
    def __init__(self, model: AudioComparisonController, identity: str) -> None:
        self.identity = identity
        fields = StateFields(
            lambda: model.mapping(identity) or AudioComparisonSource(identity),
            model.update_mapping,
        )
        super().__init__(
            identity,
            (
                SourceCaption(model.catalog, identity),
                ColumnPicker(
                    "column",
                    "Mapped audio column",
                    lambda: model.catalog.audio_choices(identity),
                    lambda: (
                        (column,) if (column := fields.read().profile.column) else ()
                    ),
                    lambda names: fields.write(
                        replace(
                            fields.read(),
                            profile=replace(
                                fields.read().profile,
                                column=next(iter(names), fields.read().profile.column),
                            ),
                        )
                    ),
                    SingleSelection(),
                ),
                AudioSamplingFields(
                    lambda: fields.read().profile,
                    lambda profile: fields.write(
                        replace(fields.read(), profile=profile)
                    ),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.identity)
        super().render(frame)
        imgui.pop_id()


class AudioComparisonTools(ComparisonTools):
    def __init__(self, model: AudioComparisonController) -> None:
        self.model = model
        fields = StateFields(lambda: model.draft, lambda s: setattr(model, "draft", s))
        view = StateFields(lambda: model.view, lambda s: setattr(model, "view", s))

        def choose_metric(metric: AudioMetric) -> None:
            view.write(
                replace(
                    view.read(),
                    metric=metric.name,
                    family=metric.family,
                    channel=metric.channel,
                )
            )

        super().__init__(
            "audio-comparison-tools",
            (
                RecipeControls(
                    model,
                    "Prepare audio comparison",
                    model.prepare,
                    lambda: JobSnapshot(
                        model.message,
                        model.jobs.busy,
                        str(model.jobs.progress.value)
                        if model.jobs.busy
                        else model.jobs.selection_message,
                    ),
                    model.abandon,
                ),
                ContributorControls(
                    model.catalog,
                    lambda: tuple(s.file_id for s in model.draft.sources),
                    model.map_files,
                    lambda source: AudioSourceForm(model, source.identity),
                ),
                fields.integer(
                    "bins",
                    "Common histogram bins",
                    lambda s: s.bins,
                    lambda s, v: replace(s, bins=v),
                    1,
                    256,
                ),
                ChoiceField(
                    "metric",
                    "Metric / unit family / channel",
                    lambda: model.metrics,
                    lambda: (
                        model.curve.metric
                        if model.curve
                        else AudioMetric("Duration", "duration", "seconds")
                    ),
                    choose_metric,
                    labels=lambda: tuple(m.label for m in model.metrics),
                ),
                view.boolean(
                    "proportion",
                    "Compare proportions",
                    lambda s: s.proportions,
                    lambda s, v: replace(s, proportions=v),
                ),
                RowLinkControls(
                    lambda: model.active.labels if model.active else (),
                    lambda: model.view.source,
                    lambda v: view.write(replace(view.read(), source=v)),
                    lambda: model.view.bin_index,
                    lambda v: view.write(replace(view.read(), bin_index=v)),
                    model.select_current,
                ),
            ),
        )

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.AUDIO

    def render(self, frame: FrameContext) -> None:
        if self.model.changed:
            imgui.text_wrapped("Unprepared audio comparison changes")
        super().render(frame)
