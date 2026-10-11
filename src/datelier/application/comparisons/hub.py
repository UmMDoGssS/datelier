"""One editor-owned comparison catalog, controller registry and persisted state."""

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.application.comparisons.audio import AudioComparisonController
from datelier.application.comparisons.base import ComparisonController, ComparisonFamily
from datelier.application.comparisons.catalog import SourceCatalog
from datelier.application.comparisons.columns import ColumnComparisonController
from datelier.application.comparisons.images import ImageComparisonController
from datelier.application.comparisons.text import TextComparisonController
from datelier.workspace.sessions import SessionWorkspace

if TYPE_CHECKING:
    from datelier.application.file import FileController


class ComparisonHub:
    def __init__(self, executor: Executor, focus: Callable[[str], None]) -> None:
        self.catalog = SourceCatalog()
        self.columns = ColumnComparisonController(self.catalog, focus, executor)
        self.text = TextComparisonController(self.catalog, focus, executor)
        self.images = ImageComparisonController(self.catalog, focus, executor)
        self.audio = AudioComparisonController(self.catalog, focus, executor)
        self.families: tuple[ComparisonController, ...] = (
            self.columns,
            self.text,
            self.images,
            self.audio,
        )
        self.tab = ComparisonFamily.COLUMNS

    def refresh(self, files: tuple[FileController, ...]) -> None:
        self.catalog.sync(files)
        for family in self.families:
            family.prune(set(self.catalog.by_id))

    def poll(self, files: tuple[FileController, ...]) -> None:
        self.refresh(files)
        for family in self.families:
            family.sync()

    def restore(self, session: SessionWorkspace) -> None:
        self.audio.jobs.clear()
        self.audio.restore(session.audio_comparisons, session.audio_comparison_index)
        self.audio.view = session.audio_comparison_view
        self.images.jobs.clear()
        self.images.restore(session.image_comparisons, session.image_comparison_index)
        self.images.view = session.image_comparison_view
        self.text.jobs.clear()
        self.text.restore(session.text_comparisons, session.text_comparison_index)
        self.text.view = session.text_comparison_view
        self.columns.jobs.clear()
        self.columns.restore(session.comparisons, session.comparison_index)
        self.columns.height = session.comparison_height
        self.columns.selected_source, self.columns.selected_bin = (
            session.comparison_source,
            session.comparison_bin,
        )
        self.tab = ComparisonFamily(
            "Text"
            if session.comparison_tab == "Text corpora"
            else session.comparison_tab
        )

    def capture(self, session: SessionWorkspace) -> SessionWorkspace:
        return replace(
            session,
            comparisons=self.columns.recipes,
            comparison_index=self.columns.index,
            comparison_height=self.columns.height,
            comparison_source=self.columns.selected_source,
            comparison_bin=self.columns.selected_bin,
            text_comparisons=self.text.recipes,
            text_comparison_index=self.text.index,
            text_comparison_view=self.text.view,
            image_comparisons=self.images.recipes,
            image_comparison_index=self.images.index,
            image_comparison_view=self.images.view,
            audio_comparisons=self.audio.recipes,
            audio_comparison_index=self.audio.index,
            audio_comparison_view=self.audio.view,
            comparison_tab="Text corpora"
            if self.tab == ComparisonFamily.TEXT
            else self.tab.value,
        )

    def close(self) -> None:
        for family in self.families:
            family.close()
        self.catalog.close()
