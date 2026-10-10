"""Adaptive plot space, an explicit height divider, and a shared expanded view."""

import math
from collections.abc import Callable
from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.gui.components.base import BoundView, FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope


@dataclass(frozen=True)
class ViewportBinding:
    label: str
    key: object
    draw_content: Callable[[float, bool], bool]
    toolbar: Callable[[], None] | None = None
    minimum_height: float = 170
    footer: Callable[[], None] | None = None
    footer_height: float = 0


@dataclass
class ResizableViewport(BoundView[ViewportBinding]):
    height: float = 0
    expanded: bool = False
    fit: bool = True
    resize_pixel: tuple[float, float] = (0, 0)
    expand_pixel: tuple[float, float] = (0, 0)
    height_pixel: tuple[float, float] = (0, 0)
    rendered_height: float = 0
    shown: bool = False
    _key: object = None
    _plot_id: int = 0
    _resize_start: float = 0
    _height_start: float = 0

    def show_content(
        self,
        label: str,
        key: object,
        draw: Callable[[float, bool], bool],
        *,
        toolbar: Callable[[], None] | None = None,
        minimum_height: float = 170,
        footer: Callable[[], None] | None = None,
        footer_height: float = 0,
    ) -> bool:
        self.bind_view(
            ViewportBinding(
                label, key, draw, toolbar, minimum_height, footer, footer_height
            )
        )
        self.render(FrameContext(ViewScope(""), GuiProbe()))
        return self.shown

    def draw(self, binding: ViewportBinding, frame: FrameContext) -> None:
        label, key, draw = binding.label, binding.key, binding.draw_content
        minimum_height, footer_height, footer = (
            binding.minimum_height,
            binding.footer_height,
            binding.footer,
        )
        if key != self._key:
            self._key = key
            self.fit = True
        if not self._plot_id:
            self._plot_id = imgui.get_id(label)
        imgui.push_id(label)
        if imgui.button("Restore" if self.expanded else "Expand"):
            self.expanded = not self.expanded
        pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
        self.expand_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
        if self.expanded:
            viewport = imgui.get_main_viewport()
            imgui.set_next_window_pos(
                (viewport.work_pos.x + 20, viewport.work_pos.y + 20),
                imgui.Cond_.appearing,
            )
            imgui.set_next_window_size(
                (viewport.work_size.x - 40, viewport.work_size.y - 40),
                imgui.Cond_.appearing,
            )
            opened, visible = imgui.begin("Expanded " + label, True)
            self.expanded = bool(visible)
            shown = False
            if opened:
                if imgui.button("Restore"):
                    self.expanded = False
                shown = self._draw(
                    draw,
                    binding.toolbar,
                    minimum_height,
                    footer_height,
                    expanded=True,
                )
                if footer is not None:
                    footer()
            imgui.end()
        else:
            shown = self._draw(
                draw,
                binding.toolbar,
                minimum_height,
                footer_height,
                expanded=False,
            )
            if footer is not None:
                footer()
        imgui.pop_id()
        self.shown = shown

    def _draw(
        self,
        draw: Callable[[float, bool], bool],
        toolbar: Callable[[], None] | None,
        minimum_height: float,
        footer_height: float,
        *,
        expanded: bool,
    ) -> bool:
        if toolbar is not None:
            toolbar()
        if not expanded:
            imgui.same_line()
            if imgui.get_content_region_avail().x < 110:
                imgui.new_line()
            imgui.text("Height")
            imgui.same_line()
            imgui.set_next_item_width(65)
            current = (
                self.height
                or self.rendered_height
                or max(minimum_height, imgui.get_content_region_avail().y - 50)
            )
            changed, value = imgui.drag_float(
                "##Viewport height", current, 1, format="%.0f px"
            )
            pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
            self.height_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
            if imgui.is_item_activated():
                self._height_start = current
            if imgui.is_item_active() and imgui.is_mouse_dragging(
                imgui.MouseButton_.left
            ):
                value = (
                    self._height_start
                    + imgui.get_mouse_drag_delta(imgui.MouseButton_.left).x
                )
                changed = True
            if changed and math.isfinite(value):
                self.height = max(minimum_height, value)
            if self.height:
                imgui.same_line()
                if imgui.get_content_region_avail().x < 40:
                    imgui.new_line()
                if imgui.button("Auto"):
                    self.height = 0
        available = imgui.get_content_region_avail().y
        height = max(
            minimum_height, available - (5 if expanded else 50) - footer_height
        )
        if not expanded and self.height:
            height = max(minimum_height, self.height)
        self.rendered_height = height
        # Stable ID across the dock and expanded window preserves native axes
        # and the 3D camera. Each chart area owns a distinct original scope.
        imgui.internal.push_override_id(self._plot_id)
        shown = draw(height, self.fit)
        imgui.pop_id()
        if shown:
            self.fit = False
        if not expanded and shown:
            imgui.button(
                "Resize view", (max(1, imgui.get_content_region_avail().x), 20)
            )
            pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
            self.resize_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
            if imgui.is_item_hovered() or imgui.is_item_active():
                imgui.set_mouse_cursor(imgui.MouseCursor_.resize_ns)
            if imgui.is_item_activated():
                self._resize_start = height
            if imgui.is_item_active() and imgui.is_mouse_dragging(
                imgui.MouseButton_.left
            ):
                self.height = max(
                    minimum_height,
                    self._resize_start
                    + imgui.get_mouse_drag_delta(imgui.MouseButton_.left).y,
                )
        return shown
