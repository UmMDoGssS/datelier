"""Prepared source/recovery feedback, independent of the source controller tree."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext


@dataclass(frozen=True)
class SourceState:
    title: str
    message: str
    loading: bool = False
    recoverable: bool = False
    deferred: bool = False


class SourceStatus(Component):
    def __init__(
        self,
        snapshot: Callable[[], SourceState],
        recover: Callable[[Path | None, bool, bool], None],
    ) -> None:
        super().__init__("source-status")
        self.snapshot, self.recover = snapshot, recover
        self.path, self.accept = "", False

    def render(self, frame: FrameContext) -> None:
        state = self.snapshot()
        if state.message:
            imgui.text_wrapped(state.message)
        if state.recoverable:
            imgui.set_next_item_width(-1)
            _, self.path = imgui.input_text_with_hint(
                "##relink", "Replacement source path", self.path
            )
            _, self.accept = imgui.checkbox("Accept changed source", self.accept)
            if imgui.button("Prepare records" if state.deferred else "Retry / relink"):
                self.recover(
                    Path(self.path) if self.path.strip() else None,
                    self.accept,
                    state.deferred,
                )


class WorkbenchNotice(Component):
    def __init__(self, message: Callable[[], str], dismiss: Callable[[], None]) -> None:
        super().__init__("notice")
        self.message, self.dismiss = message, dismiss

    def render(self, frame: FrameContext) -> None:
        message = self.message()
        if message:
            imgui.text_wrapped(message)
            imgui.same_line()
            if imgui.small_button("Dismiss"):
                self.dismiss()
