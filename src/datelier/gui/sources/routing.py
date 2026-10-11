"""Inspection and its context choose the same explicit source mode."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.native import target


class SourceInspection(Container):
    def __init__(
        self,
        record: Component,
        members: dict[str, Component],
        selected: Callable[[], str],
        choose_records: Callable[[], None],
    ) -> None:
        super().__init__("inspect-source", ())
        self.record, self.members, self.selected, self.choose_records = (
            record,
            members,
            selected,
            choose_records,
        )

    def render(self, frame: FrameContext) -> None:
        key = self.selected()
        if key:
            if imgui.button("Inspect table records"):
                self.choose_records()
            target(frame, "records")
        self.children = (self.members.get(key, self.record),)
        super().render(frame)

    def close(self) -> None:
        self.record.close()
        for child in self.members.values():
            child.close()
