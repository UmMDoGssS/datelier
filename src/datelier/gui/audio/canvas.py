"""Native signal plots; spectra upload prepared colors once per immutable result."""

from math import floor

from imgui_bundle import hello_imgui, imgui, implot

from datelier.gui.plots.area import PlotArea
from datelier.gui.plots.axes import AxisControls
from datelier.inspection.audio.mel import hz_to_mel
from datelier.inspection.audio.view_types import (
    AudioViewKind,
    PreparedSignalView,
    SpectralView,
    SpectrumScale,
    WaveformEnvelope,
)


class SignalCanvas:
    def __init__(self) -> None:
        self.area = PlotArea(height=240)
        self.textures: list[hello_imgui.TextureGpu] = []
        self.prepared: SpectralView | None = None
        self.shown = self.uploads = 0
        self.hovered: tuple[int, int] | None = None
        self.readout: tuple[float, float, float, float] | None = None
        self.bounds: tuple[float, float, float, float] | None = None
        self.peak_pixel: tuple[float, float] | None = None

    @property
    def retained_bytes(self) -> int:
        return (
            self.prepared.texture_bytes
            if self.textures and self.prepared is not None
            else 0
        )

    def clear(self) -> None:
        self.textures.clear()
        self.prepared = None
        self.bounds = None
        self.hovered = self.readout = self.peak_pixel = None

    def show(self, data: PreparedSignalView, gpu_bytes: int) -> None:
        if isinstance(data, SpectralView):
            if data.texture_bytes > gpu_bytes:
                self.clear()
                imgui.text(
                    "Spectral colors exceed texture retention; "
                    "raise memory or reduce display bins."
                )
                return
            if data is not self.prepared:
                self.clear()
                self.textures = [
                    hello_imgui.create_texture_gpu_from_rgba_data(tile.rgba)
                    for tile in data.tiles
                ]
                self.prepared = data
                self.uploads += 1
        elif self.prepared is not None:
            self.clear()
        key = (
            data.locator,
            data.range,
            data.channel,
            data.metadata.sample_rate,
            data.settings.mode,
            (data.settings.frequency_low, data.settings.frequency_high)
            if isinstance(data, SpectralView)
            else None,
        )
        if imgui.button("Fit audio axes"):
            self.area.fit = True
        self.area.show(
            "Audio signal",
            key,
            lambda height, fit, axes: self._draw(data, height, fit, axes),
            numeric_axes=(not isinstance(data, SpectralView),) * 2,
        )

    def _draw(
        self, data: PreparedSignalView, height: float, fit: bool, axes: AxisControls
    ) -> bool:
        if fit:
            implot.set_next_axes_to_fit()
        flags = implot.Flags_.no_legend if isinstance(data, SpectralView) else 0
        if not implot.begin_plot("Signal", (-1, height), flags):
            return False
        rate = data.metadata.require_rate()
        first, last = data.range.start / rate, (data.range.stop or 0) / rate
        if isinstance(data, WaveformEnvelope):
            implot.setup_axes(
                "Time (s)", f"Channel {data.channel + 1} · {data.metadata.units}"
            )
            if fit:
                implot.setup_axis_limits(
                    implot.ImAxis_.x1, first, last, imgui.Cond_.always
                )
                implot.setup_axis_limits(
                    implot.ImAxis_.y1, *data.amplitude_bounds, imgui.Cond_.always
                )
            axes.apply()
            implot.plot_shaded(
                "Original extrema",
                data.plot_times,
                data.plot_minimum,
                data.plot_maximum,
                implot.Spec(fill_alpha=0.35),
            )
            implot.plot_line("Minimum", data.plot_times, data.plot_minimum)
            implot.plot_line("Maximum", data.plot_times, data.plot_maximum)
        else:
            mel = data.settings.mode == AudioViewKind.MEL
            implot.setup_axes(
                "Time (s)", "Frequency (mel, HTK)" if mel else "Frequency (Hz)"
            )
            if fit:
                low = data.settings.frequency_low
                high = min(data.settings.frequency_high or rate / 2, rate / 2)
                implot.setup_axes_limits(
                    first,
                    last,
                    hz_to_mel(low) if mel else low,
                    hz_to_mel(high) if mel else high,
                    imgui.Cond_.always,
                )
            axes.apply()
            dx = (data.time_bounds[1] - data.time_bounds[0]) / data.power.shape[1]
            dy = (
                data.frequency_bounds[1] - data.frequency_bounds[0]
            ) / data.power.shape[0]
            for tile, texture in zip(data.tiles, self.textures, strict=True):
                x = data.time_bounds[0] + tile.column * dx
                y = data.frequency_bounds[0] + tile.row * dy
                implot.plot_image(
                    "Power density",
                    imgui.ImTextureRef(texture.texture_id()),
                    implot.Point(x, y),
                    implot.Point(
                        x + tile.rgba.shape[1] * dx, y + tile.rgba.shape[0] * dy
                    ),
                    imgui.ImVec2(0, 1),
                    imgui.ImVec2(1, 0),
                )
            row, column = data.peak
            point = implot.plot_to_pixels(
                data.time_bounds[0]
                + (column + 0.5)
                * (data.time_bounds[1] - data.time_bounds[0])
                / data.power.shape[1],
                data.frequency_bounds[0]
                + (row + 0.5)
                * (data.frequency_bounds[1] - data.frequency_bounds[0])
                / data.power.shape[0],
            )
            self.peak_pixel = (point.x, point.y)
            self._spectral_readout(data)
        limits = implot.get_plot_limits()
        low = implot.plot_to_pixels(limits.x.min, limits.y.max)
        high = implot.plot_to_pixels(limits.x.max, limits.y.min)
        self.bounds = (low.x, low.y, high.x - low.x, high.y - low.y)
        axes.observe()
        implot.end_plot()
        self.shown += 1
        return True

    def _spectral_readout(self, data: SpectralView) -> None:
        self.hovered = self.readout = None
        if not implot.is_plot_hovered():
            return
        point = implot.get_plot_mouse_pos()
        height, width = data.power.shape
        x = floor(
            (point.x - data.time_bounds[0])
            / (data.time_bounds[1] - data.time_bounds[0])
            * width
        )
        y = floor(
            (point.y - data.frequency_bounds[0])
            / (data.frequency_bounds[1] - data.frequency_bounds[0])
            * height
        )
        if not 0 <= x < width or not 0 <= y < height:
            return
        self.hovered = (x, y)
        self.readout = (
            float(data.times[x]),
            float(data.frequencies[y]),
            float(data.power[y, x]),
            float(data.values[y, x]),
        )
        time, frequency, power, value = self.readout
        mel = data.settings.mode == AudioViewKind.MEL
        units = "unit²" if mel else "unit²/Hz"
        label = (
            f"dB re 1 {units}"
            if data.settings.scale == SpectrumScale.DECIBELS
            else units
        )
        aggregation = (
            f"Peak of {data.time_step} windows · HTK mel band {y + 1}/{height}"
            if mel
            else f"Peak of {data.time_step} windows × {data.frequency_step} FFT bins"
        )
        power_label = "Band power" if mel else "PSD"
        imgui.set_tooltip(
            f"{time:.6g} s · {frequency:.6g} Hz\n"
            f"{power_label} {power:.6g}; display {value:.6g} {label}\n"
            f"{aggregation}"
        )
