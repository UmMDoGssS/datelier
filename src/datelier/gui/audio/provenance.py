"""Source and approximation notices from prepared signal-view state."""

from imgui_bundle import imgui

from datelier.inspection.audio.view_types import (
    PreparedSignalView,
    SpectralView,
    WaveformEnvelope,
)


def show_provenance(data: PreparedSignalView) -> None:
    if isinstance(data, WaveformEnvelope):
        imgui.text_wrapped(
            f"Original {data.metadata.dtype} extrema per "
            f"{data.bin_frames:,}-frame bin; "
            f"{data.nonfinite:,} nonfinite samples. Float64 plot; "
            "exact sample windows are available below."
        )
    elif isinstance(data, SpectralView):
        view = data.settings
        imgui.text_wrapped(
            f"{data.window_frames}-sample {view.window.value} window; "
            f"FFT {view.fft}; hop {view.hop}; "
            f"{data.metadata.sample_rate} Hz unchanged. Float64 PSD; no detrending."
        )
        imgui.text_wrapped(
            f"Peak of {data.time_step} windows × {data.frequency_step} FFT bins "
            f"per cell; {data.spectral_frames:,} original windows. "
            "Narrow the range or raise bins/memory for individual cells."
        )
        imgui.text_wrapped(
            f"{data.nonfinite:,} nonfinite samples replaced by zero for spectra; "
            f"{data.tail_frames} tail samples outside complete windows. "
            "Short windows zero-pad only the FFT."
        )
        imgui.text_wrapped(
            f"Colors {data.color_bounds[0]:.6g}–{data.color_bounds[1]:.6g} "
            f"({view.scale.value}); original units²/Hz, dB reference 1 unit²/Hz."
        )
