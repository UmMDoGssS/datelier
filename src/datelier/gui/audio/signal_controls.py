"""Native source-time navigation and finite signal-display recipes."""

from dataclasses import replace
from math import isfinite

from imgui_bundle import imgui

from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioMetadata, AudioRange
from datelier.inspection.audio.view_types import (
    AudioViewKind,
    AudioWindow,
    SpectrumScale,
)
from datelier.inspection.heatmaps import Colormap


def frame_input(label: str, value: int, maximum: int) -> tuple[bool, int]:
    if maximum < 2**31:
        return imgui.input_int(label, value)
    changed, number = imgui.input_double(label, float(value), format="%.0f")
    return changed, int(number) if isfinite(number) else value


def time_controls(settings: AudioSettings, metadata: AudioMetadata) -> AudioSettings:
    rate = metadata.sample_rate
    if rate is None:
        return settings
    start = min(settings.range.start, metadata.frames)
    stop = min(
        settings.range.stop if settings.range.stop is not None else metadata.frames,
        metadata.frames,
    )
    imgui.push_item_width(150)
    changed_start, first = imgui.input_double(
        "Time start (s)", start / rate, format="%.6f"
    )
    changed_stop, last = imgui.input_double("Time end (s)", stop / rate, format="%.6f")
    imgui.pop_item_width()
    if changed_start and isfinite(first):
        start = max(0, min(round(first * rate), metadata.frames))
    if changed_stop and isfinite(last):
        stop = max(start, min(round(last * rate), metadata.frames))
    if imgui.button("Whole recording"):
        start, stop = 0, metadata.frames
    imgui.same_line()
    width = max(1, stop - start)
    if imgui.button("Earlier range"):
        start = max(0, start - width)
        stop = min(start + width, metadata.frames)
    imgui.same_line()
    if imgui.button("Later range"):
        start = min(max(0, metadata.frames - width), start + width)
        stop = min(start + width, metadata.frames)
    return replace(settings, range=AudioRange(start, max(start, stop)))


def signal_controls(settings: AudioSettings) -> AudioSettings:
    view = settings.view
    kinds = list(AudioViewKind)
    for i, kind in enumerate(kinds):
        if i:
            imgui.same_line()
        if imgui.radio_button(kind.value, view.mode == kind):
            view = replace(view, mode=kind)
    if imgui.collapsing_header("Signal settings"):
        imgui.push_item_width(150)
        if view.mode == AudioViewKind.WAVEFORM:
            _, bins = imgui.input_int("Waveform display bins", view.waveform_bins)
            view = replace(view, waveform_bins=max(1, min(bins, 65536)))
        else:
            _, fft = imgui.input_int("Signal FFT length", view.fft)
            fft = 1 << (max(16, min(fft, 65536)).bit_length() - 1)
            _, hop = imgui.input_int("Signal hop length", view.hop)
            imgui.text("Periodic FFT window")
            window = view.window
            for i, candidate in enumerate(AudioWindow):
                if i:
                    imgui.same_line()
                if imgui.radio_button(candidate.value, window == candidate):
                    window = candidate
            _, low = imgui.input_double("Minimum frequency (Hz)", view.frequency_low)
            _, high = imgui.input_double(
                "Maximum frequency (Hz; 0 = Nyquist)", view.frequency_high or 0
            )
            scale = view.scale
            for i, candidate in enumerate(SpectrumScale):
                if i:
                    imgui.same_line()
                if imgui.radio_button(candidate.value, scale == candidate):
                    scale = candidate
            _, floor = imgui.input_double("Decibel floor", view.db_floor)
            _, times = imgui.input_int("Time display bins", view.time_bins)
            _, frequencies = imgui.input_int(
                "Frequency display bins", view.frequency_bins
            )
            maps = list(Colormap)
            _, choice = imgui.combo(
                "Spectral colors", maps.index(view.colormap), [m.value for m in maps]
            )
            _, automatic = imgui.checkbox(
                "Auto spectral color range", view.color_range is None
            )
            bounds = view.color_range
            if not automatic:
                first, last = bounds or (
                    (view.db_floor, 0) if scale == SpectrumScale.DECIBELS else (0, 1)
                )
                _, first = imgui.input_double("Spectral color minimum", first)
                _, last = imgui.input_double("Spectral color maximum", last)
                if isfinite(first) and isfinite(last) and first < last:
                    bounds = (first, last)
            else:
                bounds = None
            low = max(0, low) if isfinite(low) else view.frequency_low
            high = high if isfinite(high) and high > low else 0
            view = replace(
                view,
                fft=fft,
                hop=max(1, min(hop, fft)),
                window=window,
                frequency_low=low,
                frequency_high=high if high > 0 else None,
                scale=scale,
                db_floor=max(-300, min(floor, -0.001))
                if isfinite(floor)
                else view.db_floor,
                time_bins=max(1, min(times, 16384)),
                frequency_bins=max(1, min(frequencies, 32769)),
                colormap=maps[choice],
                color_range=bounds,
            )
        _, cpu = imgui.input_int("Audio memory (MiB)", settings.cpu_bytes // 1024**2)
        _, gpu = imgui.input_int(
            "Audio texture memory (MiB)", settings.gpu_bytes // 1024**2
        )
        imgui.pop_item_width()
        settings = replace(
            settings,
            cpu_bytes=max(1, min(cpu, 4096)) * 1024**2,
            gpu_bytes=max(1, min(gpu, 4096)) * 1024**2,
        )
    return replace(settings, view=view)
