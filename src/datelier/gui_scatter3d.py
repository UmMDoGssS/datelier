"""ImPlot3D renderer and projected picking/brushing of displayed source rows."""

from dataclasses import dataclass, field

import numpy as np
from imgui_bundle import imgui, implot3d
from numpy.typing import NDArray

from datelier.gui_table import TableView
from datelier.plotting import Scatter
from datelier.projection import projected_nearest, projected_rectangle
from datelier.selection import LinkedSelection

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
class Scatter3DView:
    frames: int = 0
    selected_points: int = 0
    point_pixel: tuple[float, float] = (0, 0)
    center_pixel: tuple[float, float] = (0, 0)
    press_start: tuple[float, float] | None = None
    brush_start: tuple[float, float] | None = None
    _pending_face: tuple[float, float] | None = None
    _points: Scatter | None = None
    _version: int = -1
    _selected: NDArray[np.bool_] = field(
        default_factory=lambda: np.array([], dtype=bool)
    )
    _coordinates: (
        tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]] | None
    ) = None
    _selected_coordinates: (
        tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]] | None
    ) = None
    _colors: NDArray[np.uint32] | None = None

    def show(
        self,
        points: Scatter,
        selection: LinkedSelection,
        table: TableView,
        fit: bool,
        height: float,
    ) -> bool:
        z = points.z
        if z is None:
            imgui.text_wrapped(
                "This plot has two coordinates. For raw XYZ, choose three axes "
                "and update the scatter. For an embedding, explicitly rerun "
                "with three output dimensions."
            )
            return False
        start_y = imgui.get_cursor_pos_y()
        if imgui.button("View face"):
            imgui.open_popup("3D viewing face")
        if imgui.begin_popup("3D viewing face"):
            for label, angles in FACE_VIEWS.items():
                if imgui.selectable(label, False)[0]:
                    self._pending_face = angles
                    self.press_start = self.brush_start = None
            imgui.end_popup()
        height -= imgui.get_cursor_pos_y() - start_y
        if points is not self._points or selection.version != self._version:
            if points is not self._points:
                self.press_start = self.brush_start = None
            self._points, self._version = points, selection.version
            mask = (
                np.isin(points.row_ids, tuple(selection.row_ids))
                if points.revision == selection.revision
                else np.zeros(len(z), dtype=bool)
            )
            self._selected = mask
            self._coordinates = (points.x[~mask], points.y[~mask], z[~mask])
            self._selected_coordinates = (points.x[mask], points.y[mask], z[mask])
            self._colors = (
                points.colors.rgba[~mask] if points.colors is not None else None
            )
            self.selected_points = int(mask.sum())
        flags = implot3d.Flags_.no_legend
        changing_face = self._pending_face is not None
        if changing_face:
            # A popup item can close on mouse-down over the plot. Consume that
            # gesture so choosing a face cannot also pick or move source rows.
            flags |= implot3d.Flags_.no_inputs
        if imgui.get_io().key_shift or self.brush_start is not None:
            flags |= (
                implot3d.Flags_.no_rotate
                | implot3d.Flags_.no_pan
                | implot3d.Flags_.no_zoom
            )
        if not implot3d.begin_plot("Scatter 3D", (-1, height), flags):
            return False
        implot3d.setup_axes(points.x_name, points.y_name, points.z_name)
        if self._pending_face is not None:
            # Always updates an existing camera; clearing the request lets the
            # native renderer release its rotation lock on the next frame.
            implot3d.setup_box_rotation(*self._pending_face, cond=implot3d.Cond_.always)
            self._pending_face = None
        if fit and len(z):
            bounds = []
            for array in (points.x, points.y, z):
                lo, hi = float(array.min()), float(array.max())
                pad = (hi - lo) * 0.05 if hi > lo else max(0.5, abs(lo) * 1e-6)
                bounds.extend((lo - pad, hi + pad))
            implot3d.setup_axes_limits(*bounds, cond=implot3d.Cond_.always)
        style = implot3d.Spec()
        style.marker = implot3d.Marker_.square
        style.marker_size = 1.5
        style.line_weight = 0
        # Keep colors opaque: native fill enablement follows item opacity,
        # even when an explicit marker-fill color is present.
        if self._colors is not None:
            style.marker_fill_colors = style.marker_line_colors = self._colors
        if self._coordinates is not None and len(self._coordinates[0]):
            implot3d.plot_scatter("Rows", *self._coordinates, style)
        if self._selected_coordinates is not None and len(
            self._selected_coordinates[0]
        ):
            highlight = implot3d.Spec()
            highlight.marker = implot3d.Marker_.square
            highlight.line_weight = 0
            highlight.marker_size = 2
            highlight.marker_fill_color = highlight.marker_line_color = imgui.ImVec4(
                1, 0.7, 0.2, 1
            )
            implot3d.plot_scatter(
                "Selected source rows", *self._selected_coordinates, highlight
            )
        if not changing_face:
            self._interact(points, selection, table)
        implot3d.end_plot()
        self.frames += 1
        return True

    def _project(self, points: Scatter) -> NDArray[np.float64]:
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
        )
        pixels[~valid] = np.nan
        return pixels

    def _interact(
        self, points: Scatter, selection: LinkedSelection, table: TableView
    ) -> None:
        assert points.z is not None
        pos, size = implot3d.get_plot_rect_pos(), implot3d.get_plot_rect_size()
        self.center_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
        if len(points.x):
            i = len(points.x) // 2
            pixel = implot3d.plot_to_pixels(
                float(points.x[i]), float(points.y[i]), float(points.z[i])
            )
            self.point_pixel = (pixel.x, pixel.y)
        mouse = imgui.get_mouse_pos()
        hovered = imgui.is_window_hovered(
            imgui.HoveredFlags_.allow_when_blocked_by_active_item
        ) and imgui.is_mouse_hovering_rect(
            pos, imgui.ImVec2(pos.x + size.x, pos.y + size.y)
        )
        if hovered and imgui.is_mouse_clicked(imgui.MouseButton_.left):
            if imgui.get_io().key_shift:
                self.brush_start = (mouse.x, mouse.y)
            else:
                self.press_start = (mouse.x, mouse.y)
        if self.brush_start is not None:
            start = self.brush_start
            implot3d.get_plot_draw_list().add_rect(
                imgui.ImVec2(min(start[0], mouse.x), min(start[1], mouse.y)),
                imgui.ImVec2(max(start[0], mouse.x), max(start[1], mouse.y)),
                0xFF33B3FF,
            )
            if imgui.is_mouse_released(imgui.MouseButton_.left):
                pixels = self._project(points)
                mask = projected_rectangle(pixels, start, (mouse.x, mouse.y))
                selection.choose(
                    points.revision, (int(i) for i in points.row_ids[mask])
                )
                self.brush_start = None
        if self.press_start is not None and imgui.is_mouse_released(
            imgui.MouseButton_.left
        ):
            dx, dy = mouse.x - self.press_start[0], mouse.y - self.press_start[1]
            if hovered and dx * dx + dy * dy <= 9:
                ray = implot3d.pixels_to_plot_ray(mouse.x, mouse.y)
                coordinates = np.column_stack((points.x, points.y, points.z))
                origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
                direction = np.array(
                    [ray.direction.x, ray.direction.y, ray.direction.z]
                )
                with np.errstate(over="ignore", invalid="ignore"):
                    depths = (coordinates - origin) @ direction
                index = projected_nearest(
                    self._project(points), depths, (mouse.x, mouse.y)
                )
                if index is not None and selection.choose(
                    points.revision,
                    (int(points.row_ids[index]),),
                    toggle=imgui.get_io().key_ctrl,
                ):
                    table.target_row, table.jump = (
                        int(points.positions[index]) + 1,
                        True,
                    )
            self.press_start = None
