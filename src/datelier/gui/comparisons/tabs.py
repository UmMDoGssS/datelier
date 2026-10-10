"""Comparison family and its immediate modality views."""

from abc import ABC
from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.gui.audio.comparison_view import AudioComparisonView
from datelier.gui.comparisons.view import ComparisonView
from datelier.gui.components.base import BoundView, FrameContext
from datelier.gui.editor_session import EditorSession
from datelier.gui.images.comparison_view import ImageComparisonView
from datelier.gui.text.comparison_view import TextComparisonView


class ComparisonTab(BoundView[EditorSession], ABC):
    label: str


class ColumnComparisonTab(ComparisonTab):
    label = "Columns"

    def __init__(self) -> None:
        self.view = ComparisonView()

    def draw(self, binding: EditorSession, frame: FrameContext) -> None:
        self.view.show(binding)


class TextComparisonTab(ComparisonTab):
    label = "Text"

    def __init__(self) -> None:
        self.view = TextComparisonView()

    def draw(self, binding: EditorSession, frame: FrameContext) -> None:
        self.view.show(binding)


class ImageComparisonTab(ComparisonTab):
    label = "Images"

    def __init__(self) -> None:
        self.view = ImageComparisonView()

    def draw(self, binding: EditorSession, frame: FrameContext) -> None:
        self.view.show(binding)


class AudioComparisonTab(ComparisonTab):
    label = "Audio"

    def __init__(self) -> None:
        self.view = AudioComparisonView()

    def draw(self, binding: EditorSession, frame: FrameContext) -> None:
        self.view.show(binding)


@dataclass
class ComparisonTabs(BoundView[EditorSession]):
    observed: str = ""

    def __post_init__(self) -> None:
        self.tabs: tuple[ComparisonTab, ...] = (
            ColumnComparisonTab(),
            TextComparisonTab(),
            ImageComparisonTab(),
            AudioComparisonTab(),
        )

    def draw(self, binding: EditorSession, frame: FrameContext) -> None:
        requested = (
            binding.comparison_tab if binding.comparison_tab != self.observed else ""
        )
        if requested == "Text corpora":
            requested = "Text"
        if imgui.begin_tab_bar("File comparison types"):
            for tab in self.tabs:
                flags = (
                    imgui.TabItemFlags_.set_selected if requested == tab.label else 0
                )
                if imgui.begin_tab_item(tab.label, flags=flags)[0]:
                    binding.comparison_tab = (
                        "Text corpora" if tab.label == "Text" else tab.label
                    )
                    tab.bind_view(binding)
                    tab.render(frame.child(tab.label))
                    imgui.end_tab_item()
            imgui.end_tab_bar()
        self.observed = binding.comparison_tab
