"""Signal forms compose shared typed bindings and contextual child sections."""

from dataclasses import replace

from datelier.application.media.audio import AudioController
from datelier.gui.components.inputs import StateFields
from datelier.gui.components.layout import Container
from datelier.gui.components.layout.groups import Collapsible, Conditional
from datelier.inspection.audio.signal import (
    AudioViewKind,
    AudioWindow,
    SignalViewSettings,
    SpectrumScale,
)
from datelier.inspection.heatmaps import Colormap


class SpectralDisplaySettings(Container):
    def __init__(self, fields: StateFields[SignalViewSettings]) -> None:
        super().__init__(
            "spectral-display",
            (
                fields.choice(
                    "colormap",
                    "Colors",
                    tuple(Colormap),
                    lambda s: s.colormap,
                    lambda s, v: replace(s, colormap=v),
                ),
                fields.integer(
                    "time-bins",
                    "Display time bins",
                    lambda s: s.time_bins,
                    lambda s, v: replace(s, time_bins=v),
                    1,
                    16384,
                ),
                fields.integer(
                    "frequency-bins",
                    "Display frequency bins",
                    lambda s: s.frequency_bins,
                    lambda s, v: replace(s, frequency_bins=v),
                    1,
                    32769,
                ),
                fields.boolean(
                    "range",
                    "Use display range",
                    lambda s: s.color_range is not None,
                    lambda s, v: replace(s, color_range=(-120, 0) if v else None),
                ),
                Conditional(
                    "color-range",
                    lambda: fields.read().color_range is not None,
                    (
                        fields.floating(
                            "low",
                            "Display low",
                            lambda s: (s.color_range or (-120, 0))[0],
                            lambda s, v: replace(
                                s, color_range=(v, (s.color_range or (-120, 0))[1])
                            ),
                            -1e300,
                            1e300,
                        ),
                        fields.floating(
                            "high",
                            "Display high",
                            lambda s: (s.color_range or (-120, 0))[1],
                            lambda s, v: replace(
                                s, color_range=((s.color_range or (-120, 0))[0], v)
                            ),
                            -1e300,
                            1e300,
                        ),
                    ),
                ),
            ),
        )


class SpectrumSettings(Container):
    def __init__(self, fields: StateFields[SignalViewSettings]) -> None:
        super().__init__(
            "spectrum",
            (
                fields.choice(
                    "fft",
                    "FFT frames",
                    tuple(2**i for i in range(4, 17)),
                    lambda s: s.fft,
                    lambda s, v: replace(s, fft=v),
                ),
                fields.integer(
                    "hop",
                    "Hop frames",
                    lambda s: s.hop,
                    lambda s, v: replace(s, hop=v),
                    1,
                    65536,
                ),
                fields.choice(
                    "window",
                    "Window",
                    tuple(AudioWindow),
                    lambda s: s.window,
                    lambda s, v: replace(s, window=v),
                ),
                fields.choice(
                    "scale",
                    "Scale",
                    tuple(SpectrumScale),
                    lambda s: s.scale,
                    lambda s, v: replace(s, scale=v),
                ),
                fields.floating(
                    "floor",
                    "Decibel floor",
                    lambda s: s.db_floor,
                    lambda s, v: replace(s, db_floor=v),
                    -300,
                    -0.001,
                ),
                fields.floating(
                    "low",
                    "Minimum frequency (Hz)",
                    lambda s: s.frequency_low,
                    lambda s, v: replace(s, frequency_low=v),
                ),
                fields.floating(
                    "high",
                    "Maximum frequency (0 = Nyquist)",
                    lambda s: s.frequency_high or 0,
                    lambda s, v: replace(s, frequency_high=v or None),
                ),
                Conditional(
                    "mel",
                    lambda: fields.read().mode == AudioViewKind.MEL,
                    (
                        fields.integer(
                            "bands",
                            "HTK mel bands",
                            lambda s: s.mel_bands,
                            lambda s, v: replace(s, mel_bands=v),
                            1,
                            512,
                        ),
                    ),
                ),
                Collapsible(
                    "display", "Spectral display", (SpectralDisplaySettings(fields),)
                ),
            ),
        )


class SignalSettings(Container):
    def __init__(self, model: AudioController) -> None:
        fields = StateFields(
            lambda: model.settings.view,
            lambda value: setattr(
                model, "settings", replace(model.settings, view=value)
            ),
        )
        thresholds = StateFields(
            lambda: model.settings.thresholds,
            lambda value: setattr(
                model, "settings", replace(model.settings, thresholds=value)
            ),
        )
        settings = StateFields(
            lambda: model.settings, lambda value: setattr(model, "settings", value)
        )
        super().__init__(
            "signal-settings",
            (
                fields.choice(
                    "kind",
                    "Signal view",
                    tuple(AudioViewKind),
                    lambda s: s.mode,
                    lambda s, v: replace(s, mode=v),
                ),
                Conditional(
                    "waveform",
                    lambda: fields.read().mode == AudioViewKind.WAVEFORM,
                    (
                        fields.integer(
                            "bins",
                            "Envelope bins",
                            lambda s: s.waveform_bins,
                            lambda s, v: replace(s, waveform_bins=v),
                            1,
                            65536,
                        ),
                    ),
                ),
                Conditional(
                    "spectral",
                    lambda: fields.read().mode != AudioViewKind.WAVEFORM,
                    (SpectrumSettings(fields),),
                ),
                Collapsible(
                    "thresholds",
                    "Signal thresholds and caches",
                    (
                        thresholds.floating(
                            "silence",
                            "Silence amplitude",
                            lambda s: s.silence,
                            lambda s, v: replace(s, silence=v),
                            0,
                            1e300,
                        ),
                        thresholds.floating(
                            "clipping",
                            "Clipping amplitude (0 = original rails)",
                            lambda s: s.clipping or 0,
                            lambda s, v: replace(s, clipping=v or None),
                            0,
                            1e300,
                        ),
                        settings.integer(
                            "cpu",
                            "CPU cache (MiB)",
                            lambda s: s.cpu_bytes // (1024 * 1024),
                            lambda s, v: replace(s, cpu_bytes=v * 1024 * 1024),
                            1,
                            4096,
                        ),
                        settings.integer(
                            "gpu",
                            "Texture cache (MiB)",
                            lambda s: s.gpu_bytes // (1024 * 1024),
                            lambda s, v: replace(s, gpu_bytes=v * 1024 * 1024),
                            1,
                            4096,
                        ),
                    ),
                ),
            ),
        )
