"""Audio records compose metadata, explicit commands, signal and listening children."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.media.audio import AudioController
from datelier.gui.audio.charts import SignalContent
from datelier.gui.audio.playback import PlaybackControls
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.array_table import ArrayTable
from datelier.gui.components.base import Component, FrameContext, Group
from datelier.gui.components.facts import FactsTable
from datelier.gui.components.groups import Collapsible
from datelier.gui.records.base import RecordContent
from datelier.inspection.audio.signal import SpectralView, WaveformEnvelope
from datelier.inspection.audio.types import AudioRange


class AudioMetadataView(Component):
    def __init__(self, model: AudioController) -> None:
        super().__init__("metadata")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        prepared = self.model.jobs.metadata
        if prepared:
            _, metadata = prepared
            imgui.text_wrapped(metadata.description)
            imgui.text(
                f"{metadata.frames:,} frames · {metadata.channels} channels · "
                f"{metadata.sample_rate or 'unknown'} Hz"
            )
        imgui.text_wrapped(self.model.jobs.message)


class SignalProvenance(Component):
    def __init__(self, model: AudioController) -> None:
        super().__init__("provenance")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        view = self.model.signal.active
        if view is None:
            return
        imgui.text_wrapped(
            f"Original frames [{view.range.start:,}, {view.range.stop:,}) · "
            f"channel {view.channel + 1} · {view.metadata.sample_rate} Hz · "
            f"{view.metadata.units}"
        )
        if isinstance(view, WaveformEnvelope):
            imgui.text_wrapped(
                f"Exact extrema over {view.bin_frames:,}-frame bins; "
                f"{view.nonfinite:,} nonfinite samples excluded."
            )
        elif isinstance(view, SpectralView):
            settings = view.settings
            imgui.text_wrapped(
                f"FFT {settings.fft} · hop {settings.hop} · {settings.window} · "
                f"{settings.scale} · {view.spectral_frames:,} windows · "
                f"{view.tail_frames:,} tail frames outside complete windows"
            )
            imgui.text_wrapped(
                f"Display peak aggregation: {view.time_step} windows × "
                f"{view.frequency_step} bins · {view.nonfinite:,} nonfinite samples · "
                f"{view.mel_empty_bands} empty mel bands"
            )
            imgui.text_wrapped(
                "Spectra replace nonfinite samples with zero. "
                "Short windows pad only the FFT; no detrending or resampling."
            )
            imgui.text_wrapped(
                f"Colors {view.color_bounds}; dB reference 1 original unit²/Hz, "
                "or unit² per HTK mel band."
            )


class AudioContent(RecordContent):
    def __init__(self, model: AudioController) -> None:
        super().__init__("audio")
        self.model = model
        self.signal = SignalContent(
            lambda: model.signal.active, lambda: model.settings.gpu_bytes
        )
        self.children = (
            AudioMetadataView(model),
            Group(
                "commands",
                (
                    CommandButton("retry", "Retry audio metadata", model.jobs.abandon),
                    CommandButton(
                        "waveform",
                        "Prepare signal view",
                        model.request_signal,
                        lambda: bool(
                            model.jobs.metadata and model.jobs.metadata[1].sample_rate
                        ),
                    ),
                    CommandButton(
                        "profile",
                        "Profile original signal",
                        model.request_profile,
                        lambda: bool(
                            model.jobs.metadata and model.jobs.metadata[1].sample_rate
                        ),
                    ),
                    JobFeedback(
                        "profile-job",
                        lambda: JobSnapshot(
                            model.jobs.message if model.jobs.profiling else "",
                            model.jobs.profiling,
                            str(model.jobs.progress.value)
                            if model.jobs.profiling
                            else "",
                        ),
                        model.abandon_profile,
                    ),
                    JobFeedback(
                        "signal-job",
                        lambda: JobSnapshot(model.signal.message, model.signal.busy),
                        model.abandon_signal,
                    ),
                ),
            ),
            self.signal,
            SignalProvenance(model),
            Collapsible(
                "statistics",
                "Exact signal statistics",
                (
                    FactsTable(
                        "totals",
                        ("Statistic", "Value"),
                        lambda: model.signal_statistics,
                        150,
                    ),
                    FactsTable(
                        "channels",
                        (
                            "Channel",
                            "Minimum",
                            "Maximum",
                            "Peak",
                            "Mean",
                            "RMS",
                            "Clipped",
                            "Silent",
                            "Finite",
                            "Nonfinite",
                            "Samples",
                        ),
                        lambda: model.channel_statistics,
                        120,
                    ),
                ),
            ),
            Collapsible(
                "samples",
                "Exact original sample window",
                (
                    CommandButton(
                        "samples", "Prepare original samples", model.request_samples
                    ),
                    ArrayTable(
                        "raw-samples",
                        lambda: model.jobs.active.raw if model.jobs.active else None,
                        lambda: (
                            model.jobs.active.range.start if model.jobs.active else 0
                        ),
                    ),
                ),
            ),
            Collapsible(
                "listening", "Listen to original audio", (PlaybackControls(model),)
            ),
        )

    def render(self, frame: FrameContext) -> None:
        card = self.card
        if card is None or card.primary is None:
            return
        model = self.model
        model.request_record(card.primary.name, card.position)
        prepared = model.jobs.metadata
        if prepared:
            metadata = prepared[1]
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
        self.signal.height, self.signal.fit = self.height, self.fit
        super().render(frame)
        self.fit = self.signal.fit
