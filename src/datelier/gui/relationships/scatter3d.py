"""3D scatter components own camera gestures and bounded projected row input."""

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from imgui_bundle import imgui, implot3d
from numpy.typing import NDArray

from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.fields import ChoiceField
from datelier.gui.components.native import help_tip, target
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.relationships.primitives import (
    draw_color_items,
    legend_hovered,
    with_color_scale,
)
from datelier.gui.relationships.summary import ScatterSummary
from datelier.plotting.scatter import (
    LinkedSelection,
    Scatter,
    projected_nearest,
    projected_rectangle,
)

FACE_VIEWS: dict[str, tuple[float, float]] = {
    "Isometric": (30, -45),
    "Top (XY)": (90, 0),
    "Bottom (XY)": (-90, 0),
    "Front (XZ)": (0, 0),
    "Back (XZ)": (0, 180),
    "Left (YZ)": (0, 90),
    "Right (YZ)": (0, -90),
}


@dataclass
class CameraState:
    face: str = "Isometric"
    pending: bool = False
    press: tuple[float, float] | None = None
    brush: tuple[float, float] | None = None
    visible: NDArray[np.bool_] = field(default_factory=lambda: np.array([], dtype=bool))

    def choose(self, face: str) -> None:
        self.face, self.pending = face, True
        self.press = self.brush = None


class CameraFaceChoice(ChoiceField[str]):
    def __init__(self, state: CameraState) -> None:
        super().__init__(
            "face", "Viewing face", tuple(FACE_VIEWS), lambda: state.face, state.choose
        )
        self.state = state

    def render(self, frame: FrameContext) -> None:
        super().render(frame)
        target(frame, "face-" + self.state.face)


class ProjectedInput(Component):
    def __init__(
        self,
        prepared: Callable[[], Scatter | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
        state: CameraState,
    ) -> None:
        super().__init__("input")
        self.prepared, self.selection, self.jump, self.state = (
            prepared,
            selection,
            jump,
            state,
        )

    def project(self, points: Scatter) -> NDArray[np.float64]:
        assert points.z is not None
        pixels = np.array(
            [
                (p.x, p.y)
                for p in (
                    implot3d.plot_to_pixels(float(x), float(y), float(z))
                    for x, y, z in zip(points.x, points.y, points.z, strict=True)
                )
            ],
            dtype=np.float64,
        ).reshape(-1, 2)
        pos, size = implot3d.get_plot_rect_pos(), implot3d.get_plot_rect_size()
        valid = (
            (pixels[:, 0] >= pos.x)
            & (pixels[:, 0] <= pos.x + size.x)
            & (pixels[:, 1] >= pos.y)
            & (pixels[:, 1] <= pos.y + size.y)
            & self.state.visible
        )
        pixels[~valid] = np.nan
        return pixels

    def render(self, frame: FrameContext) -> None:
        points = self.prepared()
        if points is None or points.z is None:
            return
        pos, size = implot3d.get_plot_rect_pos(), implot3d.get_plot_rect_size()
        mouse = imgui.get_mouse_pos()
        state = self.state
        frame.record("center", (pos.x + size.x / 2, pos.y + size.y / 2))
        if len(points.x):
            i = len(points.x) // 2
            p = implot3d.plot_to_pixels(
                float(points.x[i]), float(points.y[i]), float(points.z[i])
            )
            frame.record("point", (p.x, p.y))
        hovered = (
            imgui.is_window_hovered(
                imgui.HoveredFlags_.allow_when_blocked_by_active_item
            )
            and not legend_hovered(three_d=True)
            and imgui.is_mouse_hovering_rect(
                pos, imgui.ImVec2(pos.x + size.x, pos.y + size.y)
            )
        )
        if hovered and imgui.is_mouse_clicked(imgui.MouseButton_.left):
            if imgui.get_io().key_shift:
                state.brush = (mouse.x, mouse.y)
            else:
                state.press = (mouse.x, mouse.y)
        if state.brush is not None:
            a = state.brush
            implot3d.get_plot_draw_list().add_rect(
                (min(a[0], mouse.x), min(a[1], mouse.y)),
                (max(a[0], mouse.x), max(a[1], mouse.y)),
                0xFF33B3FF,
            )
            if imgui.is_mouse_released(imgui.MouseButton_.left):
                mask = projected_rectangle(self.project(points), a, (mouse.x, mouse.y))
                self.selection.choose(
                    points.revision, (int(i) for i in points.row_ids[mask])
                )
                state.brush = None
        if state.press is not None and imgui.is_mouse_released(imgui.MouseButton_.left):
            dx, dy = mouse.x - state.press[0], mouse.y - state.press[1]
            if hovered and dx * dx + dy * dy <= 9:
                ray = implot3d.pixels_to_plot_ray(mouse.x, mouse.y)
                with np.errstate(over="ignore", invalid="ignore"):
                    depths = (
                        np.column_stack((points.x, points.y, points.z))
                        - np.array([ray.origin.x, ray.origin.y, ray.origin.z])
                    ) @ np.array([ray.direction.x, ray.direction.y, ray.direction.z])
                index = projected_nearest(
                    self.project(points), depths, (mouse.x, mouse.y)
                )
                if index is not None and self.selection.choose(
                    points.revision,
                    (int(points.row_ids[index]),),
                    toggle=imgui.get_io().key_ctrl,
                ):
                    self.jump(int(points.positions[index]))
            state.press = None


class NativeScatter3D(Container):
    def __init__(
        self,
        prepared: Callable[[], Scatter | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
        state: CameraState,
    ) -> None:
        super().__init__("canvas", (ProjectedInput(prepared, selection, jump, state),))
        self.prepared, self.selection, self.state = prepared, selection, state
        self.height = 200.0
        self.fit = True

    def draw(self, width: float, frame: FrameContext) -> bool:
        points = self.prepared()
        if points is None or points.z is None:
            return False
        changing_face = self.state.pending
        flags = implot3d.Flags_.no_inputs if changing_face else 0
        if imgui.get_io().key_shift or self.state.brush is not None:
            flags |= (
                implot3d.Flags_.no_rotate
                | implot3d.Flags_.no_pan
                | implot3d.Flags_.no_zoom
            )
        if not implot3d.begin_plot("##scatter3d", (width, self.height), flags):
            return False
        implot3d.setup_axes(points.x_name, points.y_name, points.z_name)
        if changing_face:
            implot3d.setup_box_rotation(
                *FACE_VIEWS[self.state.face], cond=implot3d.Cond_.always
            )
            self.state.pending = False
        if self.fit and len(points.x):
            bounds = []
            for values in (points.x, points.y, points.z):
                lo, hi = float(values.min()), float(values.max())
                pad = (hi - lo) * 0.05 if hi > lo else max(0.5, abs(lo) * 1e-6)
                bounds.extend((lo - pad, hi + pad))
            implot3d.setup_axes_limits(*bounds, cond=implot3d.Cond_.always)
        chosen = self.selection.mask(points)
        self.state.visible = draw_color_items(points, chosen, three_d=True)
        selected = chosen & self.state.visible
        frame.measure("selected", (float(selected.sum()), float(len(selected))))
        if selected.any():
            implot3d.plot_scatter(
                "Selected source rows",
                points.x[selected],
                points.y[selected],
                points.z[selected],
                implot3d.Spec(
                    marker=implot3d.Marker_.square,
                    line_weight=0,
                    marker_size=2,
                    marker_fill_color=(1, 0.7, 0.2, 1),
                    marker_line_color=(1, 0.7, 0.2, 1),
                    flags=implot3d.ItemFlags_.no_legend,
                ),
            )
        if not changing_face:
            super().render(frame)
        implot3d.end_plot()
        target(frame, "plot")
        self.fit = False
        return True

    def render(self, frame: FrameContext) -> None:
        points = self.prepared()
        if points:
            with_color_scale(points, self.height, lambda width: self.draw(width, frame))


class Scatter3DPlot(ViewportContent):
    def __init__(
        self,
        prepared: Callable[[], Scatter | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__("scatter3d")
        self.prepared, self.selection = prepared, selection
        self.state = CameraState()
        self._stamp: tuple[object, ...] = ()
        self._points: Scatter | None = None
        self.canvas = NativeScatter3D(prepared, selection, jump, self.state)
        self.children = (
            ScatterSummary(prepared, selection),
            CameraFaceChoice(self.state),
            self.canvas,
        )

    def render(self, frame: FrameContext) -> None:
        points = self.prepared()
        if points is None or points.z is None:
            imgui.text_wrapped(
                "Choose three numeric features or explicitly prepare "
                "a 3D analysis result."
            )
            return
        stamp = points.revision, points.x_name, points.y_name, points.z_name
        if stamp != self._stamp:
            self._stamp, self.fit = stamp, True
            self.state.press = self.state.brush = None
        if points is not self._points:
            self._points = points
            self.state.press = self.state.brush = None
        self.canvas.height, self.canvas.fit = (
            max(120, self.height - 90),
            self.fit or self.canvas.fit,
        )
        super().render(frame)
        self.fit = self.canvas.fit
        help_tip(
            "Right drag rotates, left drag pans, wheel zooms. Click selects; "
            "Ctrl-click toggles; Shift-drag brushes visible projected points."
        )

    def close(self) -> None:
        self._stamp = ()
        self._points = None
        self.state.visible = np.array([], dtype=bool)
        self.state.press = self.state.brush = None
        super().close()
