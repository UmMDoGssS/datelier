"""One virtual table family for prepared frames and immutable record sequences."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import number, target


class VirtualTable(Component, ABC):
    def __init__(
        self,
        key: str,
        height: float = 240,
        open_row: Callable[[int], None] | None = None,
        action_label: str = "Open",
    ) -> None:
        super().__init__(key)
        self.height, self.open_row = height, open_row
        self.action_label = action_label

    @abstractmethod
    def bind(self) -> tuple[tuple[str, ...], int]: ...

    @abstractmethod
    def row(self, index: int) -> tuple[object, ...]: ...

    def render(self, frame: FrameContext) -> None:
        columns, count = self.bind()
        if not columns:
            return
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.scroll_x
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.sizing_fixed_fit
        )
        if imgui.begin_table(
            self.key, len(columns) + bool(self.open_row), flags, (-1, self.height)
        ):
            if self.open_row:
                imgui.table_setup_column(
                    "Action", imgui.TableColumnFlags_.width_fixed, 65
                )
            for name in columns:
                imgui.table_setup_column(name, imgui.TableColumnFlags_.width_fixed, 130)
            imgui.table_setup_scroll_freeze(0, 1)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(count)
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    imgui.table_next_row()
                    if self.open_row:
                        imgui.table_next_column()
                        if imgui.small_button(f"{self.action_label}##{index}"):
                            self.open_row(index)
                        target(frame, f"open-{index}")
                    for value in self.row(index):
                        imgui.table_next_column()
                        text = number(value)
                        imgui.text_unformatted(text[:256])
                        if len(text) > 256 and imgui.is_item_hovered():
                            imgui.set_tooltip(
                                text[:4096]
                                + ("… (preview truncated)" if len(text) > 4096 else "")
                            )
            imgui.end_table()


class SequenceTable[T](VirtualTable):
    def __init__(
        self,
        key: str,
        headers: tuple[str, ...],
        items: Callable[[], tuple[T, ...]],
        values: Callable[[T], tuple[object, ...]],
        height: float = 240,
        open_row: Callable[[int], None] | None = None,
        action_label: str = "Open",
    ) -> None:
        super().__init__(key, height, open_row, action_label)
        self.headers, self.items, self.values = headers, items, values
        self._items: tuple[T, ...] = ()

    def bind(self) -> tuple[tuple[str, ...], int]:
        self._items = self.items()
        return self.headers, len(self._items)

    def row(self, index: int) -> tuple[object, ...]:
        return self.values(self._items[index])

    def close(self) -> None:
        self._items = ()
