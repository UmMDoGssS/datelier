"""Focused audio records with worker headers, explicit profiles and exact windows."""

from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.audio.canvas import SignalCanvas
from datelier.gui.audio.listening import ListeningControls
from datelier.gui.audio.provenance import show_provenance
from datelier.gui.audio.signal_controls import (
    frame_input,
    signal_controls,
    time_controls,
)
from datelier.gui.audio.statistics import show_statistics
from datelier.inspection.audio.jobs import AudioJobs
from datelier.inspection.audio.playback.controller import AudioPlayback
from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.audio.view_jobs import SignalViewJobs
from datelier.inspection.audio.view_types import AudioViewKind
from datelier.io.types import ArrayOptions

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class AudioView:
    def __init__(
        self, executor: Executor | None = None, playback: AudioPlayback | None = None
    ) -> None:
        self.jobs = AudioJobs(executor)
        self.signal = SignalViewJobs(executor)
        self.canvas = SignalCanvas()
        self.player = (
            playback if playback is not None else AudioPlayback(executor=executor)
        )
        self._owns_player = playback is None
        self.listening = ListeningControls(self.player)
        self.settings = AudioSettings()
        self.buttons: dict[str, tuple[float, float]] = {}
        self.rendered_samples = 0

    def sync(self, owner: FileSession) -> None:
        active = owner.loader.active
        self.jobs.sync(
            owner.identity,
            owner.view_name,
            active.dataset.revision if active else None,
            owner.references.settings,
            owner.references.index,
        )
        self.jobs.cpu_bytes = self.settings.cpu_bytes
        self.jobs.poll()
        self.player.devices.poll()
        records = owner.inspect.jobs.active
        prepared = self.jobs.metadata
        if (
            prepared is not None
            and prepared[0].catalog is not None
            and prepared[1].sample_rate != self.settings.array_sample_rate
        ):
            prepared = None
        if prepared is not None and records is not None:
            focus = min(owner.inspect.settings.focus, max(0, len(records.row_ids) - 1))
            if (
                not len(records.row_ids)
                or int(records.row_ids[focus]) != prepared[0].origin.row_id
            ):
                prepared = None
        self.listening.sync(owner.identity, prepared, self.settings)
        self.signal.bind(self.jobs.metadata)
        self.signal.poll()
        if self.signal.active is None:
            self.canvas.clear()

    def show_record(self, owner: FileSession, column: str, position: int) -> None:
        active = owner.loader.active
        if active is None:
            return
        options = active.imported.options
        mapping = options.mapping if isinstance(options, ArrayOptions) else None
        self.jobs.request_record(
            active.dataset,
            column,
            position,
            active.imported.array_catalog,
            mapping,
            self.settings.array_sample_rate,
        )
        if mapping is not None:
            _, rate = imgui.input_int(
                "Array sample rate (Hz; 0 = unknown)",
                self.settings.array_sample_rate or 0,
            )
            self.settings = replace(
                self.settings, array_sample_rate=min(768000, rate) if rate > 0 else None
            )
        if self.button("Retry audio"):
            self.jobs.abandon()
        imgui.text_wrapped(self.jobs.message)
        prepared = self.jobs.metadata
        if prepared is None:
            return
        _, metadata = prepared
        imgui.text_wrapped(metadata.description)
        imgui.text(
            f"{metadata.frames:,} sample frames · {metadata.channels:,} channels · "
            + (
                f"{metadata.duration:.6g} s"
                if metadata.duration is not None
                else "duration unknown"
            )
        )
        if self.jobs.active is None and self.jobs.profile is None:
            imgui.text_wrapped("Choose a command to prepare samples or statistics.")
        self._controls(metadata.frames, metadata.channels)
        self.settings = time_controls(self.settings, metadata)
        self.settings = self.listening.show(prepared, self.settings, owner.arrays.store)
        self.settings = signal_controls(self.settings)
        start = min(self.settings.range.start, metadata.frames)
        stop = min(
            self.settings.range.stop
            if self.settings.range.stop is not None
            else metadata.frames,
            metadata.frames,
        )
        selected = AudioRange(start, max(start, stop))
        if metadata.sample_rate is not None:
            self._signal(owner, selected)
        if self.button("Prepare sample window"):
            self.jobs.request_window(selected, owner.arrays.store)
        imgui.begin_disabled(metadata.sample_rate is None)
        if self.button("Profile complete audio"):
            self.jobs.request_profile(
                AudioRange(), self.settings.thresholds, owner.arrays.store
            )
        imgui.same_line()
        if self.button("Profile selected range"):
            self.jobs.request_profile(
                selected, self.settings.thresholds, owner.arrays.store
            )
        imgui.end_disabled()
        if metadata.sample_rate is None:
            imgui.text_wrapped(
                "Set the array sample rate to prepare time-based statistics."
            )
        if self.jobs.profiling:
            done, total = self.jobs.progress.value
            imgui.text(f"Profiling {done:,}/{total:,} sample frames")
            if self.button("Abandon audio profiling"):
                self.jobs.abandon_profile()
                self.jobs.message = (
                    "Profiling abandoned; executing reads are winding down."
                )
        if self.jobs.profile is not None:
            show_statistics(self.jobs.profile)
        self._samples()

    def _controls(self, frames: int, channels: int) -> None:
        settings = self.settings
        start = min(settings.range.start, frames)
        stop = min(
            settings.range.stop if settings.range.stop is not None else frames, frames
        )
        imgui.push_item_width(150)
        _, start = frame_input("First sample frame", start, frames)
        _, stop = frame_input("End sample frame (exclusive)", stop, frames)
        _, channel = imgui.input_int(
            "Sample channel (1-based)", min(settings.channel, channels - 1) + 1
        )
        imgui.pop_item_width()
        thresholds = settings.thresholds
        changed, automatic = imgui.checkbox(
            "Use original clipping rails", thresholds.clipping is None
        )
        clipping = None if automatic else thresholds.clipping or 1.0
        if not automatic:
            _, clipping_value = imgui.input_double(
                "Clipping amplitude", clipping or 1.0
            )
            clipping = max(1e-12, min(clipping_value, 1e300))
        _, silence = imgui.input_double("Silence amplitude", thresholds.silence)
        configured = AudioThresholds(clipping, max(0.0, min(silence, 1e300)))
        if configured != thresholds:
            self.jobs.abandon_profile()
        start = max(0, min(start, frames))
        selected = AudioRange(start, max(start, min(stop, frames)))
        self.settings = replace(
            settings,
            range=selected,
            channel=max(0, min(channel - 1, channels - 1)),
            thresholds=configured,
        )

    def _signal(self, owner: FileSession, selected: AudioRange) -> None:
        settings = self.settings
        budget = (
            settings.cpu_bytes
            if settings.view.mode == AudioViewKind.WAVEFORM
            else min(settings.cpu_bytes, settings.gpu_bytes * 5)
        )
        try:
            self.signal.request(
                selected, settings.channel, settings.view, owner.arrays.store, budget
            )
        except ValueError as error:
            self.signal.message = str(error)
        if self.button("Retry signal view"):
            self.signal.abandon()
        imgui.text_wrapped(self.signal.message)
        if self.signal.busy:
            done, total = self.signal.progress.value
            imgui.text(f"Signal preparation {done:,}/{total:,} frames")
        data = self.signal.active
        if data is None:
            return
        show_provenance(data)
        self.canvas.area.height = settings.plot_height
        self.canvas.show(data, settings.gpu_bytes)
        self.settings = replace(self.settings, plot_height=self.canvas.area.height)
        if self.button("Inspect visible time range"):
            low, high = self.canvas.area.axes.limits[0]
            rate = data.metadata.require_rate()
            start = max(0, min(round(low * rate), data.metadata.frames))
            stop = max(start, min(round(high * rate), data.metadata.frames))
            self.settings = replace(self.settings, range=AudioRange(start, stop))

    def _samples(self) -> None:
        self.rendered_samples = 0
        prepared = self.jobs.active
        if prepared is None:
            return
        imgui.text_wrapped(
            f"Original samples: frames {prepared.range.start:,}–"
            f"{prepared.range.stop:,}; "
            f"{prepared.retained_bytes:,} bytes retained."
        )
        channel = min(self.settings.channel, prepared.metadata.channels - 1)
        if imgui.begin_table(
            "Exact audio samples",
            3,
            imgui.TableFlags_.scroll_y | imgui.TableFlags_.borders,
            (0, 170),
        ):
            for name in (
                "Sample frame",
                "Time (s)",
                f"Channel {channel + 1} · {prepared.metadata.dtype}",
            ):
                imgui.table_setup_column(name)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(len(prepared.raw))
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    frame = prepared.range.start + index
                    self.rendered_samples += 1
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text(str(frame))
                    imgui.table_next_column()
                    imgui.text(
                        f"{frame / prepared.metadata.sample_rate:.9g}"
                        if prepared.metadata.sample_rate
                        else "unknown"
                    )
                    imgui.table_next_column()
                    imgui.text(str(prepared.raw[index, channel]))
            imgui.end_table()

    def button(self, label: str) -> bool:
        clicked = imgui.button(label)
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.buttons[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        return clicked

    def close(self, file_id: str | None = None) -> None:
        if self._owns_player:
            self.player.close(wait=False)
        elif file_id is not None:
            self.player.stop(file_id)
        self.canvas.clear()
        self.signal.close()
        self.jobs.close()
        self.buttons.clear()
