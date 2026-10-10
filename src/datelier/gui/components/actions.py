"""Common explicit commands and prepared job feedback."""

from collections.abc import Callable
from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import target


class CommandButton(Component):
    def __init__(
        self,
        key: str,
        label: str,
        command: Callable[[], object],
        enabled: Callable[[], bool] = lambda: True,
    ) -> None:
        super().__init__(key)
        self.label, self.command, self.enabled = label, command, enabled
        self.error = ""

    def render(self, frame: FrameContext) -> None:
        imgui.begin_disabled(not self.enabled())
        if imgui.button(self.label + "##" + self.key):
            try:
                self.command()
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        target(frame, "run")
        imgui.end_disabled()
        if self.error:
            imgui.text_wrapped(self.error)


@dataclass(frozen=True)
class JobSnapshot:
    message: str
    busy: bool = False
    detail: str = ""


class JobFeedback(Component):
    def __init__(
        self,
        key: str,
        snapshot: Callable[[], JobSnapshot],
        cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(key)
        self.snapshot, self.cancel = snapshot, cancel

    def render(self, frame: FrameContext) -> None:
        state = self.snapshot()
        if state.message:
            imgui.text_wrapped(state.message)
        if state.detail:
            imgui.text_wrapped(state.detail)
        if state.busy and self.cancel is not None:
            if imgui.button("Cancel##" + self.key):
                self.cancel()
            target(frame, "cancel")
