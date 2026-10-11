"""One page-owned comparison composition, shared by every file tab."""

from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.comparisons.hub import ComparisonHub
from datelier.gui.comparisons.column_tools import ColumnComparisonTools
from datelier.gui.comparisons.columns import ColumnComparisonContent
from datelier.gui.comparisons.image_tools import ImageComparisonTools
from datelier.gui.comparisons.images import ImageComparisonContent
from datelier.gui.comparisons.text import TextComparisonContent
from datelier.gui.comparisons.text_tools import TextComparisonTools
from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.routing import RoutedContent
from datelier.gui.shell.navigation import CanvasTabs, NamedTab


class PendingFamily(Component):
    def __init__(self, family: ComparisonFamily) -> None:
        super().__init__(family.value)
        self.family = family

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(f"{self.family} comparison reconstruction is pending.")


@dataclass
class CompareComponents:
    canvas: Component
    settings: Component

    def close(self) -> None:
        self.canvas.close()
        self.settings.close()


def assemble_comparisons(model: ComparisonHub) -> CompareComponents:
    content = {
        ComparisonFamily.COLUMNS: ColumnComparisonContent(model.columns),
        ComparisonFamily.TEXT: TextComparisonContent(model.text),
        ComparisonFamily.IMAGES: ImageComparisonContent(model.images),
    }
    settings: dict[str, Component] = {
        ComparisonFamily.COLUMNS: ColumnComparisonTools(model.columns),
        ComparisonFamily.TEXT: TextComparisonTools(model.text),
        ComparisonFamily.IMAGES: ImageComparisonTools(model.images),
    }
    canvas = CanvasTabs(
        tuple(
            NamedTab(family.value, content.get(family) or PendingFamily(family))
            for family in ComparisonFamily
        ),
        lambda: model.tab.value,
        lambda value: setattr(model, "tab", ComparisonFamily(value)),
    )
    return CompareComponents(canvas, RoutedContent(settings, lambda: model.tab.value))
