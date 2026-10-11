"""Related signal charts use prepared extrema or worker-colored spectral tiles."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from math import floor

from imgui_bundle import hello_imgui, imgui, implot

from datelier.gui.components.layout import FrameContext
from datelier.gui.components.layout.viewport import ViewportContent
from datelier.inspection.audio.signal import (
    AudioViewKind,
    PreparedSignalView,
    SpectralView,
    WaveformEnvelope,
)
from datelier.inspection.audio.signal.mel import hz_to_mel


class SignalChart(ViewportContent, ABC):
    @property
    @abstractmethod
    def kind(self) -> AudioViewKind: ...


class WaveformChart(SignalChart):
    def __init__(self, prepared: Callable[[], WaveformEnvelope | None]) -> None:
        super().__init__("waveform")
        self.prepared = prepared

    @property
    def kind(self) -> AudioViewKind:
        return AudioViewKind.WAVEFORM

    def render(self, frame: FrameContext) -> None:
        view = self.prepared()
        if view is None:
            return
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##waveform", (-1, self.height)):
            implot.setup_axes("Original time (s)", view.metadata.units)
            implot.plot_shaded(
                "Original extrema",
                view.plot_times,
                view.plot_minimum,
                view.plot_maximum,
                implot.Spec(fill_alpha=0.35),
            )
            implot.plot_line("Minimum", view.plot_times, view.plot_minimum)
            implot.plot_line("Maximum", view.plot_times, view.plot_maximum)
            if implot.is_plot_hovered() and len(view.starts):
                time = implot.get_plot_mouse_pos().x
                index = max(
                    0,
                    min(
                        len(view.starts) - 1,
                        int(
                            (time * view.metadata.require_rate() - view.range.start)
                            // view.bin_frames
                        ),
                    ),
                )
                imgui.set_tooltip(
                    f"Original frames [{view.starts[index]}, {view.stops[index]})\n"
                    f"Extrema {view.minimum[index]} / {view.maximum[index]}\n"
                    f"{view.finite[index]} finite samples"
                )
            implot.end_plot()
            self.fit = False


class SpectralChart(SignalChart):
    def __init__(
        self, prepared: Callable[[], SpectralView | None], budget: Callable[[], int]
    ) -> None:
        super().__init__("spectrum")
        self.prepared, self.budget = prepared, budget
        self.textures: list[hello_imgui.TextureGpu] = []
        self.uploaded: SpectralView | None = None

    @property
    def kind(self) -> AudioViewKind:
        return AudioViewKind.SPECTROGRAM

    def clear(self) -> None:
        self.textures.clear()
        self.uploaded = None

    def render(self, frame: FrameContext) -> None:
        view = self.prepared()
        if view is None:
            self.clear()
            return
        if view.texture_bytes > self.budget():
            self.clear()
            imgui.text_wrapped(
                "Spectral colors exceed the texture budget. "
                "Reduce display bins or raise the cache limit."
            )
            return
        if view is not self.uploaded:
            self.clear()
            self.textures = [
                hello_imgui.create_texture_gpu_from_rgba_data(tile.rgba)
                for tile in view.tiles
            ]
            self.uploaded = view
            self.fit = True
        mel = view.settings.mode == AudioViewKind.MEL
        if implot.begin_plot("##spectrum", (-1, self.height), implot.Flags_.no_legend):
            implot.setup_axes(
                "Original time (s)", "Frequency (mel, HTK)" if mel else "Frequency (Hz)"
            )
            if self.fit:
                rate = view.metadata.require_rate()
                high = min(view.settings.frequency_high or rate / 2, rate / 2)
                low = view.settings.frequency_low
                implot.setup_axes_limits(
                    view.range.start / rate,
                    (view.range.stop or 0) / rate,
                    hz_to_mel(low) if mel else low,
                    hz_to_mel(high) if mel else high,
                    imgui.Cond_.always,
                )
            dx = (view.time_bounds[1] - view.time_bounds[0]) / view.power.shape[1]
            dy = (
                view.frequency_bounds[1] - view.frequency_bounds[0]
            ) / view.power.shape[0]
            for tile, texture in zip(view.tiles, self.textures, strict=True):
                x, y = (
                    view.time_bounds[0] + tile.column * dx,
                    view.frequency_bounds[0] + tile.row * dy,
                )
                implot.plot_image(
                    "Original-rate power",
                    imgui.ImTextureRef(texture.texture_id()),
                    implot.Point(x, y),
                    implot.Point(
                        x + tile.rgba.shape[1] * dx, y + tile.rgba.shape[0] * dy
                    ),
                    imgui.ImVec2(0, 1),
                    imgui.ImVec2(1, 0),
                )
            if implot.is_plot_hovered():
                point = implot.get_plot_mouse_pos()
                rows, columns = view.power.shape
                x = floor(
                    (point.x - view.time_bounds[0])
                    / (view.time_bounds[1] - view.time_bounds[0])
                    * columns
                )
                y = floor(
                    (point.y - view.frequency_bounds[0])
                    / (view.frequency_bounds[1] - view.frequency_bounds[0])
                    * rows
                )
                if 0 <= x < columns and 0 <= y < rows:
                    imgui.set_tooltip(
                        f"{view.times[x]:.6g} s · {view.frequencies[y]:.6g} Hz\n"
                        f"{'Band power (unit²)' if mel else 'PSD (unit²/Hz)'}: "
                        f"{view.power[y, x]:.6g}\nDisplay: {view.values[y, x]:.6g}\n"
                        f"Peak aggregation: {view.time_step} windows × "
                        f"{view.frequency_step} bins"
                    )
            implot.end_plot()
            self.fit = False

    def close(self) -> None:
        self.clear()
        super().close()


class SignalContent(ViewportContent):
    def __init__(
        self,
        prepared: Callable[[], PreparedSignalView | None],
        budget: Callable[[], int],
    ) -> None:
        super().__init__("signal")
        self.prepared = prepared
        self.waveform = WaveformChart(
            lambda: value if isinstance(value := prepared(), WaveformEnvelope) else None
        )
        self.spectral = SpectralChart(
            lambda: value if isinstance(value := prepared(), SpectralView) else None,
            budget,
        )
        self.registry = {
            AudioViewKind.WAVEFORM: self.waveform,
            AudioViewKind.SPECTROGRAM: self.spectral,
            AudioViewKind.MEL: self.spectral,
        }
        self._active: PreparedSignalView | None = None

    def render(self, frame: FrameContext) -> None:
        view = self.prepared()
        if view is None:
            self._active = None
            self.children = ()
            self.spectral.clear()
            return
        if view is not self._active:
            self._active = view
            self.fit = True
        child = self.registry[view.settings.mode]
        if child is self.waveform:
            self.spectral.clear()
        child.height, child.fit = self.height, self.fit
        self.children = (child,)
        super().render(frame)
        self.fit = child.fit

    def close(self) -> None:
        self._active = None
        self.spectral.close()
