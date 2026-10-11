"""Virtual exact values from a bounded worker-owned matrix, without table copies."""

from collections.abc import Callable

import numpy as np
from imgui_bundle import imgui
from numpy.typing import NDArray

from datelier.gui.components.layout import Component, FrameContext


class ArrayTable(Component):
    def __init__(
        self,
        key: str,
        values: Callable[[], NDArray[np.generic] | None],
        start: Callable[[], int],
        height: float = 180,
    ) -> None:
        super().__init__(key)
        self.values, self.start, self.height = values, start, height
        self.column_start = 0

    def render(self, frame: FrameContext) -> None:
        values = self.values()
        if values is None or values.ndim != 2:
            return
        columns = values.shape[1]
        if columns > 32:
            _, self.column_start = imgui.slider_int(
                "Channel window", self.column_start, 0, max(0, columns - 32)
            )
        self.column_start = min(self.column_start, max(0, columns - 32))
        shown = min(32, columns - self.column_start)
        if shown and imgui.begin_table(
            "samples",
            shown + 1,
            imgui.TableFlags_.scroll_x
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg,
            (-1, self.height),
        ):
            imgui.table_setup_column("Original frame")
            for channel in range(self.column_start, self.column_start + shown):
                imgui.table_setup_column(f"Channel {channel + 1}")
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(values.shape[0])
            while clipper.step():
                for row in range(clipper.display_start, clipper.display_end):
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text(str(self.start() + row))
                    for channel in range(self.column_start, self.column_start + shown):
                        imgui.table_next_column()
                        imgui.text_unformatted(str(values[row, channel]))
            imgui.end_table()
