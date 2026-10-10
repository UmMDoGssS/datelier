"""One searchable, virtualized picker used by every column-selection tool."""

from collections.abc import Callable
from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.application.columns import (
    ColumnChoice,
    SelectionPolicy,
    SingleSelection,
)
from datelier.gui.components.base import BoundView, Component, FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope


@dataclass(frozen=True)
class ChecklistBinding:
    choices: tuple[ColumnChoice, ...]
    search: str
    selected: Callable[[], tuple[str, ...]]
    toggle: Callable[[str], None]
    permitted: Callable[[str], bool]


class ColumnChoiceRow(Component):
    def __init__(self, choice: ColumnChoice, binding: ChecklistBinding) -> None:
        self.choice, self.binding = choice, binding

    def render(self, frame: FrameContext) -> None:
        choice = self.choice
        imgui.push_id(choice.name)
        imgui.begin_disabled(
            not choice.enabled or not self.binding.permitted(choice.name)
        )
        changed, _ = imgui.checkbox(choice.name, choice.name in self.binding.selected())
        imgui.end_disabled()
        low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        frame.record(choice.name, ((low.x + high.x) / 2, (low.y + high.y) / 2))
        if choice.reason and imgui.is_item_hovered(
            imgui.HoveredFlags_.allow_when_disabled
        ):
            imgui.set_tooltip(choice.reason)
        if changed:
            self.binding.toggle(choice.name)
        imgui.pop_id()


class ColumnChecklist(BoundView[ChecklistBinding]):
    def draw(self, binding: ChecklistBinding, frame: FrameContext) -> None:
        query = binding.search.casefold()
        names = tuple(c for c in binding.choices if query in c.name.casefold())
        if imgui.begin_child("Choices", (-1, -1)):
            for group in dict.fromkeys(c.group for c in names):
                items = tuple(c for c in names if c.group == group)
                if group:
                    imgui.separator_text(group)
                clipper = imgui.ListClipper()
                clipper.begin(len(items), imgui.get_frame_height_with_spacing())
                while clipper.step():
                    for index in range(clipper.display_start, clipper.display_end):
                        ColumnChoiceRow(items[index], binding).render(frame)
        imgui.end_child()


@dataclass(frozen=True)
class ColumnPickerBinding:
    choices: tuple[ColumnChoice, ...]
    selected: tuple[str, ...]
    caption: str
    bulk_label: str = "Select all"


class ColumnPicker(BoundView[ColumnPickerBinding]):
    def __init__(self, key: str, policy: SelectionPolicy) -> None:
        self.key, self.policy = key, policy
        self.search = ""
        self.value: tuple[str, ...] = ()
        self.checklist = ColumnChecklist()
        self.probe = GuiProbe()

    def show(
        self,
        choices: tuple[ColumnChoice, ...],
        selected: tuple[str, ...],
        *,
        caption: str | None = None,
        bulk_label: str = "Select all",
        frame: FrameContext | None = None,
    ) -> tuple[str, ...]:
        self.value = selected
        self.bind_view(
            ColumnPickerBinding(choices, selected, caption or self.key, bulk_label)
        )
        self.probe.begin_frame()
        self.render(frame or FrameContext(ViewScope(""), self.probe))
        return self.value

    def draw(self, binding: ColumnPickerBinding, frame: FrameContext) -> None:
        self.value = binding.selected
        label = (
            self.value[0]
            if isinstance(self.policy, SingleSelection) and self.value
            else binding.caption
        )
        if imgui.button(label + "###" + self.key, (-1, 0)):
            imgui.open_popup(self.key + " checklist")
        low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        frame.record(self.key, ((low.x + high.x) / 2, (low.y + high.y) / 2))
        viewport = imgui.get_main_viewport()
        extent = (
            min(350, viewport.work_size.x - 20),
            min(360, viewport.work_size.y - 20),
        )
        imgui.set_next_window_size_constraints(extent, extent)
        if not imgui.begin_popup(self.key + " checklist"):
            return
        if not isinstance(self.policy, SingleSelection):
            if imgui.button(binding.bulk_label):
                self.value = self.policy.bulk(binding.choices)
            imgui.same_line()
            if imgui.button("Clear"):
                self.value = ()
            imgui.same_line()
        if imgui.button("Done"):
            imgui.close_current_popup()
        imgui.set_next_item_width(-1)
        _, self.search = imgui.input_text("Find column", self.search)

        def toggle(name: str) -> None:
            self.value = self.policy.toggle(binding.choices, self.value, name)
            if isinstance(self.policy, SingleSelection):
                imgui.close_current_popup()

        def permitted(name: str) -> bool:
            choice = next(c for c in binding.choices if c.name == name)
            return self.policy.permits(choice, self.value)

        self.checklist.bind_view(
            ChecklistBinding(
                binding.choices, self.search, lambda: self.value, toggle, permitted
            )
        )
        self.checklist.render(frame.child(self.key).child("choices"))
        imgui.end_popup()


class SingleColumnPicker(ColumnPicker):
    def __init__(self, key: str) -> None:
        super().__init__(key, SingleSelection())

    def choose(
        self, names: tuple[str, ...], selected: str | None
    ) -> tuple[bool, str | None]:
        value = self.show(
            tuple(ColumnChoice(name) for name in names),
            (selected,) if selected is not None else (),
            caption="Choose column",
        )
        chosen = value[0] if value else None
        return chosen != selected, chosen
