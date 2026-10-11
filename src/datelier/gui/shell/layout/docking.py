"""Outer native windows and default docking are owned by one container."""

from imgui_bundle import imgui

from datelier.gui.components.layout import Component, Container, FrameContext, Panel


class DockPanel(Panel):
    def __init__(self, key: str, label: str, content: Component) -> None:
        super().__init__(key, (content,))
        self.label = label
        self.visible = True
        self.drawer = False

    def render(self, frame: FrameContext) -> None:
        if not self.visible:
            return
        if self.drawer:
            viewport = imgui.get_main_viewport()
            imgui.set_next_window_pos(
                (
                    viewport.work_pos.x + viewport.work_size.x - 300,
                    viewport.work_pos.y + 45,
                ),
                imgui.Cond_.always,
            )
            imgui.set_next_window_size(
                (290, viewport.work_size.y - 60), imgui.Cond_.always
            )
        flags = imgui.WindowFlags_.no_docking if self.drawer else 0
        opened, visible = imgui.begin(self.label, True, flags)
        self.visible = bool(visible)
        if opened:
            position, size = imgui.get_window_pos(), imgui.get_window_size()
            frame.record("scroll", (position.x + size.x - 9, position.y + size.y / 2))
            frame.record("clip-start", (position.x + 8, position.y + 36))
            frame.record(
                "clip-end", (position.x + size.x - 8, position.y + size.y - 12)
            )
            imgui.push_id(frame.scope.file_id + "/" + frame.scope.view_id)
            super().render(frame)
            imgui.pop_id()
        imgui.end()


class DockHost(Container):
    def __init__(
        self, source: DockPanel, canvas: DockPanel, context: DockPanel, table: DockPanel
    ) -> None:
        super().__init__("workbench", (source, canvas, context, table))
        self.source, self.canvas, self.context, self.table = (
            source,
            canvas,
            context,
            table,
        )
        self.initialized = False
        self.compact = False
        self.customized = False
        self.reset = False
        self._signature: dict[str, int] = {}
        self._geometry: dict[str, tuple[float, float]] = {}
        self._work_size = (0.0, 0.0)
        self._settle = 4

    def toggle_context(self) -> None:
        self.context.visible = not self.context.visible

    def toggle_table(self) -> None:
        self.table.visible = not self.table.visible

    def render(self, frame: FrameContext) -> None:
        width = imgui.get_main_viewport().work_size.x
        if self.reset:
            self.customized = False
        compact = width < 1100 and not self.customized
        node_id = imgui.get_id("Datelier workbench")
        if (
            not self.initialized
            or self.reset
            or (not self.customized and compact != self.compact)
        ):
            self._build(node_id, compact)
            self.initialized = True
            self.compact = compact
            self.reset = False
            self._settle = 4
        imgui.dock_space(node_id, (0, 0))
        self.context.drawer = compact
        super().render(frame)
        windows = {
            panel.key: window
            for panel in self.children
            if isinstance(panel, DockPanel) and panel.visible and not panel.drawer
            for window in (imgui.internal.find_window_by_name(panel.label),)
            if window is not None
        }
        signature = {key: window.dock_id for key, window in windows.items()}
        geometry = {
            key: (window.size.x, window.size.y) for key, window in windows.items()
        }
        size = imgui.get_main_viewport().work_size
        work_size = (size.x, size.y)
        if work_size != self._work_size or signature.keys() != self._signature.keys():
            self._settle = max(self._settle, 4)
        if self._settle:
            self._settle -= 1
        elif any(
            key in self._signature and self._signature[key] != dock_id
            for key, dock_id in signature.items()
        ) or (
            imgui.is_mouse_down(0)
            and any(
                key in self._geometry
                and any(
                    abs(a - b) > 1
                    for a, b in zip(value, self._geometry[key], strict=True)
                )
                for key, value in geometry.items()
            )
        ):
            self.customized = True
        self._signature = signature
        self._geometry = geometry
        self._work_size = work_size

    def _build(self, node_id: int, compact: bool) -> None:
        imgui.internal.dock_builder_remove_node(node_id)
        imgui.internal.dock_builder_add_node(
            node_id, imgui.internal.DockNodeFlagsPrivate_.dock_space
        )
        size = imgui.get_content_region_avail()
        imgui.internal.dock_builder_set_node_size(node_id, size)
        _, left, center = imgui.internal.dock_builder_split_node_py(
            node_id, imgui.Dir.left, min(0.3, 220 / max(1, size.x))
        )
        if not compact:
            _, right, center = imgui.internal.dock_builder_split_node_py(
                center, imgui.Dir.right, min(0.4, 280 / max(1, size.x - 220))
            )
            imgui.internal.dock_builder_dock_window(self.context.label, right)
        self.context.visible = not compact
        _, bottom, center = imgui.internal.dock_builder_split_node_py(
            center, imgui.Dir.down, min(0.5, 240 / max(1, size.y))
        )
        for panel, node in (
            (self.source, left),
            (self.canvas, center),
            (self.table, bottom),
        ):
            imgui.internal.dock_builder_dock_window(panel.label, node)
        imgui.internal.dock_builder_finish(node_id)
