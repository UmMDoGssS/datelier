"""Shared native viewport sizing and direct-child content composition."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.native import target


class ViewportContent(Container):
    def __init__(self, key: str) -> None:
        super().__init__(key, ())
        self.height = 200.0
        self.fit = True


class ResizableViewport(Container):
    def __init__(
        self,
        key: str,
        content: ViewportContent,
        height: float = 0,
        minimum: float = 170,
        read_height: Callable[[], float] | None = None,
        write_height: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(key, (content,))
        self.content = content
        self.read_height, self.write_height = read_height, write_height
        self._height, self.minimum = height, minimum
        self.expanded = False
        self._native_id = 0
        self._start = 0.0

    @property
    def height(self) -> float:
        return self.read_height() if self.read_height else self._height

    @height.setter
    def height(self, value: float) -> None:
        self._height = value
        if self.write_height:
            self.write_height(value)

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        if not self._native_id:
            self._native_id = imgui.get_id("content")
        if imgui.button("Restore" if self.expanded else "Expand"):
            self.expanded = not self.expanded
        target(frame, "expand")
        imgui.same_line()
        if imgui.button("Auto"):
            self.height = 0
        target(frame, "auto")
        imgui.same_line()
        if imgui.button("Fit"):
            self.content.fit = True
        target(frame, "fit")
        if self.expanded:
            viewport = imgui.get_main_viewport()
            imgui.set_next_window_pos(
                (viewport.work_pos.x + 12, viewport.work_pos.y + 12),
                imgui.Cond_.appearing,
            )
            imgui.set_next_window_size(
                (viewport.work_size.x - 24, viewport.work_size.y - 24),
                imgui.Cond_.appearing,
            )
            opened, visible = imgui.begin("Expanded view##" + self.key, True)
            self.expanded = bool(visible)
            if opened:
                if imgui.button("Restore"):
                    self.expanded = False
                target(frame, "restore")
                self._render_content(frame, True)
            imgui.end()
        else:
            self._render_content(frame, False)
        imgui.pop_id()

    def _render_content(self, frame: FrameContext, expanded: bool) -> None:
        automatic = max(self.minimum, imgui.get_content_region_avail().y - 32)
        self.content.height = automatic if expanded or not self.height else self.height
        frame.measure("extent", (self.content.height, float(expanded)))
        imgui.internal.push_override_id(self._native_id)
        super().render(frame)
        imgui.pop_id()
        if not expanded:
            imgui.button("##resize", (-1, 12))
            target(frame, "resize")
            if imgui.is_item_hovered() or imgui.is_item_active():
                imgui.set_mouse_cursor(imgui.MouseCursor_.resize_ns)
            if imgui.is_item_activated():
                self._start = self.content.height
            if imgui.is_item_active() and imgui.is_mouse_dragging(
                imgui.MouseButton_.left
            ):
                self.height = max(
                    self.minimum, self._start + imgui.get_mouse_drag_delta().y
                )
