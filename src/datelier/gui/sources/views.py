"""Named record view selection receives identities and commands only."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import label_text, target


class RecordViewSelector(Component):
    def __init__(
        self,
        choices: Callable[[], tuple[tuple[str | None, str], ...]],
        active: Callable[[], str | None],
        choose: Callable[[str | None], None],
        close: Callable[[str], None],
    ) -> None:
        super().__init__("record-views")
        self.choices, self.active, self.choose, self.close_view = (
            choices,
            active,
            choose,
            close,
        )

    def render(self, frame: FrameContext) -> None:
        choices = self.choices()
        if len(choices) <= 1:
            return
        active = self.active()
        index = next(
            (i for i, (identity, _) in enumerate(choices) if identity == active), 0
        )
        changed, index = imgui.combo(
            "Record view", index, [label_text(label) for _, label in choices]
        )
        target(frame, "select")
        if changed:
            self.choose(choices[index][0])
        if active is not None:
            if imgui.button("Close record view"):
                self.close_view(active)
            target(frame, "close")
