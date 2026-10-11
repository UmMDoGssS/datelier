"""One page-owned comparison composition, shared by every file tab."""

from dataclasses import dataclass

from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.comparisons.hub import ComparisonHub
from datelier.gui.comparisons.audio import AudioComparisonContent
from datelier.gui.comparisons.audio_tools import AudioComparisonTools
from datelier.gui.comparisons.column_tools import ColumnComparisonTools
from datelier.gui.comparisons.columns import ColumnComparisonContent
from datelier.gui.comparisons.image_tools import ImageComparisonTools
from datelier.gui.comparisons.images import ImageComparisonContent
from datelier.gui.comparisons.text import TextComparisonContent
from datelier.gui.comparisons.text_tools import TextComparisonTools
from datelier.gui.components.base import Component
from datelier.gui.components.routing import RoutedContent
from datelier.gui.shell.navigation import CanvasTabs, NamedTab


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
        ComparisonFamily.AUDIO: AudioComparisonContent(model.audio),
    }
    settings: dict[str, Component] = {
        ComparisonFamily.COLUMNS: ColumnComparisonTools(model.columns),
        ComparisonFamily.TEXT: TextComparisonTools(model.text),
        ComparisonFamily.IMAGES: ImageComparisonTools(model.images),
        ComparisonFamily.AUDIO: AudioComparisonTools(model.audio),
    }
    canvas = CanvasTabs(
        tuple(NamedTab(family.value, content[family]) for family in ComparisonFamily),
        lambda: model.tab.value,
        lambda value: setattr(model, "tab", ComparisonFamily(value)),
    )
    return CompareComponents(canvas, RoutedContent(settings, lambda: model.tab.value))
