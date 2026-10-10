"""One searchable column selector for single and multiple tool drafts."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.columns import ColumnChoice, SelectionPolicy
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.native import target


class ColumnRow(Component):
    def __init__(
        self,
        choice: ColumnChoice,
        selected: bool,
        enabled: bool,
        toggle: Callable[[str], None],
    ) -> None:
        super().__init__(choice.name)
        self.choice, self.selected, self.enabled, self.toggle = (
            choice,
            selected,
            enabled,
            toggle,
        )

    def render(self, frame: FrameContext) -> None:
        imgui.begin_disabled(not self.enabled)
        clicked, _ = imgui.checkbox(self.choice.name, self.selected)
        target(frame, "select")
        if clicked:
            self.toggle(self.choice.name)
        imgui.end_disabled()
        if self.choice.reason and imgui.is_item_hovered():
            imgui.set_tooltip(self.choice.reason)


class ColumnList(Container):
    def __init__(
        self,
        choices: Callable[[], tuple[ColumnChoice, ...]],
        selected: Callable[[], tuple[str, ...]],
        changed: Callable[[tuple[str, ...]], None],
        policy: SelectionPolicy,
    ) -> None:
        super().__init__("list", ())
        self.choices, self.selected, self.changed, self.policy = (
            choices,
            selected,
            changed,
            policy,
        )
        self.search = ""
        self.group = "All roles"

    def toggle(self, name: str) -> None:
        self.changed(self.policy.toggle(self.choices(), self.selected(), name))

    def render(self, frame: FrameContext) -> None:
        imgui.set_next_item_width(-1)
        _, self.search = imgui.input_text_with_hint(
            "##search", "Search columns", self.search
        )
        groups = [
            "All roles",
            *dict.fromkeys(c.group for c in self.choices() if c.group),
        ]
        imgui.set_next_item_width(-1)
        _, group = imgui.combo(
            "##role", groups.index(self.group) if self.group in groups else 0, groups
        )
        self.group = groups[group]
        shown = tuple(
            c
            for c in self.choices()
            if self.search.casefold() in c.name.casefold()
            and (self.group == "All roles" or c.group == self.group)
        )
        if imgui.button("Select shown"):
            self.changed(self.policy.bulk(shown))
        target(frame, "bulk")
        imgui.same_line()
        if imgui.button("Clear"):
            self.changed(())
        target(frame, "clear")
        if imgui.begin_child("choices", (0, 180)):
            clipper = imgui.ListClipper()
            clipper.begin(len(shown), imgui.get_frame_height_with_spacing())
            while clipper.step():
                self.children = tuple(
                    ColumnRow(
                        choice,
                        choice.name in self.selected(),
                        self.policy.permits(choice, self.selected()),
                        self.toggle,
                    )
                    for choice in shown[clipper.display_start : clipper.display_end]
                )
                super().render(frame)
        imgui.end_child()


class ColumnPicker(Container):
    def __init__(
        self,
        key: str,
        label: str,
        choices: Callable[[], tuple[ColumnChoice, ...]],
        selected: Callable[[], tuple[str, ...]],
        changed: Callable[[tuple[str, ...]], None],
        policy: SelectionPolicy,
    ) -> None:
        super().__init__(key, (ColumnList(choices, selected, changed, policy),))
        self.label, self.selected = label, selected

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        imgui.text(self.label)
        names = self.selected()
        caption = ", ".join(names[:2]) + (
            f" +{len(names) - 2}" if len(names) > 2 else ""
        )
        if imgui.button((caption or "Choose columns") + "##open", (-1, 0)):
            imgui.open_popup("picker")
        target(frame, "open")
        imgui.set_next_window_size((330, 310), imgui.Cond_.appearing)
        if imgui.begin_popup("picker"):
            super().render(frame)
            imgui.end_popup()
        imgui.pop_id()
