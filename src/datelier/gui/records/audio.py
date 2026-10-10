"""Original audio metadata and explicitly prepared waveform content."""

from dataclasses import fields, replace

from imgui_bundle import imgui, implot

from datelier.application.audio import AudioController
from datelier.gui.components.base import FrameContext
from datelier.gui.components.native import target
from datelier.gui.records.base import RecordContent
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.audio.view_types import WaveformEnvelope


class AudioContent(RecordContent):
    def __init__(self, model: AudioController) -> None:
        super().__init__("audio")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        card = self.card
        if card is None or card.primary is None:
            return
        model = self.model
        model.request_record(card.primary.name, card.position)
        imgui.text_wrapped(model.jobs.message)
        prepared = model.jobs.metadata
        if prepared is None:
            return
        _, metadata = prepared
        imgui.text_wrapped(metadata.description)
        imgui.text(
            f"{metadata.frames:,} frames · {metadata.channels} channels · "
            f"{metadata.sample_rate or 'unknown'} Hz"
        )
        selected = model.settings.range
        start = min(metadata.frames, max(0, selected.start))
        stop = (
            metadata.frames
            if selected.stop is None
            else min(metadata.frames, selected.stop)
        )
        model.settings = replace(
            model.settings, range=AudioRange(start, max(start, stop))
        )
        imgui.begin_disabled(metadata.sample_rate is None)
        if imgui.button("Prepare waveform"):
            model.request_signal()
        target(frame, "waveform")
        imgui.same_line()
        if imgui.button("Profile original signal"):
            model.request_profile()
        target(frame, "profile")
        imgui.end_disabled()
        imgui.text_wrapped(model.signal.message)
        view = model.signal.active
        if isinstance(view, WaveformEnvelope):
            if self.fit:
                implot.set_next_axes_to_fit()
            if implot.begin_plot("##waveform", (-1, max(170, self.height - 100))):
                implot.setup_axes("Original time (s)", metadata.units)
                implot.plot_shaded(
                    "Original extrema",
                    view.plot_times,
                    view.plot_minimum,
                    view.plot_maximum,
                    implot.Spec(fill_alpha=0.35),
                )
                implot.plot_line("Minimum", view.plot_times, view.plot_minimum)
                implot.plot_line("Maximum", view.plot_times, view.plot_maximum)
                implot.end_plot()
                self.fit = False
        profile = model.jobs.profile
        if profile:
            if imgui.collapsing_header("Signal statistics"):
                for field in fields(profile):
                    imgui.text_wrapped(f"{field.name}: {getattr(profile, field.name)}")
