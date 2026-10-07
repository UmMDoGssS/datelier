"""Native explicit listening controls over the application-owned output worker."""

from dataclasses import replace
from math import isfinite

from imgui_bundle import imgui

from datelier.inspection.audio.playback.controller import AudioPlayback, PlaybackPhase
from datelier.inspection.audio.playback.types import PlaybackRequest
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange
from datelier.io.arrays.storage import ArrayStore

ACTIVE_PHASES = (PlaybackPhase.STARTING, PlaybackPhase.PLAYING, PlaybackPhase.PAUSED)


def playback_request(
    prepared: tuple[AudioLocator, AudioMetadata], settings: AudioSettings
) -> PlaybackRequest:
    locator, metadata = prepared
    start = min(settings.range.start, metadata.frames)
    stop = min(
        settings.range.stop if settings.range.stop is not None else metadata.frames,
        metadata.frames,
    )
    selected = (
        AudioRange(start, max(start, stop))
        if settings.playback.selected_range
        else AudioRange(0, metadata.frames)
    )
    return PlaybackRequest(
        locator,
        metadata,
        selected,
        channel=min(settings.channel, metadata.channels - 1)
        if settings.playback.selected_channel
        else None,
        device=settings.playback.device,
        cpu_bytes=settings.cpu_bytes,
    )


class ListeningControls:
    def __init__(self, player: AudioPlayback) -> None:
        self.player = player

    def sync(
        self,
        file_id: str,
        prepared: tuple[AudioLocator, AudioMetadata] | None,
        settings: AudioSettings,
    ) -> None:
        state = self.player.snapshot
        request = state.request
        if (
            request is None
            or request.locator.origin.file_id != file_id
            or state.phase not in ACTIVE_PHASES
        ):
            return
        if prepared is None or replace(request, start_frame=None) != playback_request(
            prepared, settings
        ):
            self.player.stop(file_id)

    def start(
        self,
        prepared: tuple[AudioLocator, AudioMetadata],
        settings: AudioSettings,
        arrays: ArrayStore,
    ) -> None:
        request = playback_request(prepared, settings)
        first, last = request.range.bounds(request.metadata.frames)
        cursor = settings.playback.seek_frame
        if cursor is not None:
            request = replace(request, start_frame=max(first, min(cursor, last)))
        self.player.play(request, arrays, volume=settings.playback.volume)

    def show(
        self,
        prepared: tuple[AudioLocator, AudioMetadata],
        settings: AudioSettings,
        arrays: ArrayStore,
    ) -> AudioSettings:
        locator, metadata = prepared
        prefs = settings.playback
        if not imgui.collapsing_header("Playback", imgui.TreeNodeFlags_.default_open):
            return settings
        _, selected = imgui.checkbox("Play selected range", prefs.selected_range)
        imgui.same_line()
        _, channel = imgui.checkbox("Listen selected channel", prefs.selected_channel)
        prefs = replace(prefs, selected_range=selected, selected_channel=channel)
        self.player.devices.poll()
        if imgui.button("Check audio outputs"):
            self.player.devices.request()
        imgui.same_line()
        preview = prefs.device or "Default output"
        if imgui.begin_combo("Audio output", preview):
            if imgui.selectable("Default output", prefs.device is None)[0]:
                prefs = replace(prefs, device=None)
            for choice in self.player.devices.choices:
                if imgui.selectable(choice.query, prefs.device == choice.query)[0]:
                    prefs = replace(prefs, device=choice.query)
            imgui.end_combo()
        imgui.text_wrapped(self.player.devices.message)
        changed, volume = imgui.slider_float(
            "Playback volume", prefs.volume, 0, 1, "%.3f"
        )
        if changed and isfinite(volume):
            prefs = replace(prefs, volume=max(0, min(volume, 1)))
            state = self.player.snapshot
            if (
                state.request is not None
                and state.request.locator.origin.file_id == locator.origin.file_id
            ):
                self.player.set_volume(prefs.volume)
        settings = replace(settings, playback=prefs)
        self.sync(locator.origin.file_id, prepared, settings)
        expected = playback_request(prepared, settings)
        state = self.player.snapshot
        matched = (
            state.request is not None
            and replace(state.request, start_frame=None) == expected
        )
        rate = metadata.sample_rate
        imgui.begin_disabled(rate is None)
        if imgui.button(
            "Resume audio"
            if matched and state.phase == PlaybackPhase.PAUSED
            else "Play audio"
        ):
            try:
                if matched and state.phase == PlaybackPhase.PAUSED:
                    self.player.pause(False)
                else:
                    self.start(prepared, settings, arrays)
            except (ValueError, RuntimeError) as error:
                imgui.text_wrapped(str(error))
        imgui.same_line()
        imgui.begin_disabled(not matched or state.phase != PlaybackPhase.PLAYING)
        if imgui.button("Pause audio"):
            self.player.pause()
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Stop audio"):
            self.player.stop(locator.origin.file_id)
        first, last = expected.range.bounds(metadata.frames)
        if rate is not None:
            cursor = max(
                first,
                min(prefs.seek_frame if prefs.seek_frame is not None else first, last),
            )
            _, seek = imgui.input_double("Seek time (s)", cursor / rate, format="%.6f")
            if isfinite(seek):
                seek = max(first / rate, min(seek, last / rate))
                prefs = replace(
                    prefs, seek_frame=max(first, min(round(seek * rate), last))
                )
            if imgui.button("Seek audio"):
                try:
                    if matched and state.phase in ACTIVE_PHASES:
                        self.player.seek(prefs.seek_frame or first)
                except (ValueError, RuntimeError) as error:
                    imgui.text_wrapped(str(error))
            position = state.position if matched else prefs.seek_frame or first
            imgui.progress_bar(
                (position - first) / max(1, last - first),
                (-1, 0),
                f"{position / rate:.3f} s · {first / rate:.3f}–{last / rate:.3f} s",
            )
        imgui.end_disabled()
        if matched or state.phase == PlaybackPhase.FAILED:
            imgui.text_wrapped(f"{state.phase.value}: {state.message}")
            if state.device:
                imgui.text_wrapped(
                    f"Output {state.device}; latency {state.latency * 1000:.1f} ms; "
                    f"{state.underruns} underruns."
                )
            if state.conversion:
                imgui.text_wrapped(
                    f"{state.conversion}; gain then clipping at ±1 for output only. "
                    f"{state.nonfinite} nonfinite values silenced. "
                    "Cursor shows submitted samples."
                )
        return replace(settings, playback=prefs)
