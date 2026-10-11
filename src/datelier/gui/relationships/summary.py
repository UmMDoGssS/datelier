"""Shared prepared scatter facts and explicit selection clearing."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import target
from datelier.plotting.data import Scatter
from datelier.plotting.selection import LinkedSelection


class ScatterSummary(Component):
    def __init__(
        self, prepared: Callable[[], Scatter | None], selection: LinkedSelection
    ) -> None:
        super().__init__("summary")
        self.prepared, self.selection = prepared, selection

    def render(self, frame: FrameContext) -> None:
        points = self.prepared()
        if points is None:
            return
        imgui.text_wrapped(
            f"{len(points.x):,} displayed of {points.eligible_rows:,} eligible · "
            f"{points.total_rows - points.eligible_rows:,} excluded · "
            f"{len(self.selection.row_ids):,} selected"
        )
        if points.colors and points.colors.note:
            imgui.text_wrapped(points.colors.note)
        if self.selection.row_ids:
            if imgui.small_button("Clear selection"):
                self.selection.choose(points.revision, ())
            target(frame, "clear")
