"""Shared comparison recipe commands, feedback and scoped row-link controls."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.comparisons.base import RecipeController
from datelier.application.comparisons.catalog import SourceCatalog
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Component, FrameContext, Group
from datelier.gui.components.fields import ChoiceField, IntegerField


class SourceCaption(Component):
    def __init__(self, catalog: SourceCatalog, identity: str) -> None:
        super().__init__("caption")
        self.catalog, self.identity = catalog, identity

    def render(self, frame: FrameContext) -> None:
        source = self.catalog.by_id.get(self.identity)
        imgui.separator_text(source.title if source else self.identity)


class RecipeControls[Recipe](Group):
    def __init__(
        self,
        model: RecipeController[Recipe],
        action: str,
        command: Callable[[], None],
        snapshot: Callable[[], JobSnapshot],
        cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            "recipe-controls",
            (
                ChoiceField(
                    "recipe",
                    "Comparison",
                    lambda: tuple(range(len(model.recipes))),
                    lambda: model.index,
                    model.choose,
                    labels=lambda: tuple(
                        f"Comparison {i + 1}" for i in range(len(model.recipes))
                    ),
                ),
                CommandButton("new", "New comparison", model.new),
                CommandButton(
                    "remove",
                    "Remove comparison",
                    model.remove,
                    lambda: bool(model.recipes),
                ),
                CommandButton("apply", action, command),
                JobFeedback("job", snapshot, cancel),
            ),
        )


class RowLinkControls(Group):
    def __init__(
        self,
        labels: Callable[[], tuple[str, ...]],
        source: Callable[[], int],
        choose_source: Callable[[int], None],
        bin_index: Callable[[], int],
        choose_bin: Callable[[int], None],
        select: Callable[[], None],
    ) -> None:
        super().__init__(
            "row-links",
            (
                ChoiceField(
                    "source",
                    "Link rows in source",
                    lambda: tuple(range(len(labels()))),
                    source,
                    choose_source,
                    labels=labels,
                ),
                IntegerField("bin", "Bin / category (0-based)", bin_index, choose_bin),
                CommandButton(
                    "select", "Select matching rows", select, lambda: bool(labels())
                ),
            ),
        )
