"""One editor-owned comparison catalog, controller registry and persisted state."""

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.comparisons.catalog import SourceCatalog
from datelier.application.comparisons.columns import ColumnComparisonController
from datelier.workspace.session_types import SessionWorkspace

if TYPE_CHECKING:
    from datelier.application.file import FileController


class ComparisonHub:
    def __init__(self, executor: Executor, focus: Callable[[str], None]) -> None:
        self.catalog = SourceCatalog()
        self.columns = ColumnComparisonController(self.catalog, focus, executor)
        self.tab = ComparisonFamily.COLUMNS

    def refresh(self, files: tuple[FileController, ...]) -> None:
        self.catalog.sync(files)
        self.columns.prune(set(self.catalog.by_id))

    def poll(self, files: tuple[FileController, ...]) -> None:
        self.refresh(files)
        self.columns.sync()

    def restore(self, session: SessionWorkspace) -> None:
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
        identities = set(self.catalog.by_id)
        return replace(
            session,
            comparisons=self.columns.recipes,
            comparison_index=self.columns.index,
            comparison_height=self.columns.height,
            comparison_source=self.columns.selected_source,
            comparison_bin=self.columns.selected_bin,
            text_comparisons=tuple(
                replace(
                    recipe,
                    sources=tuple(s for s in recipe.sources if s.file_id in identities),
                )
                for recipe in session.text_comparisons
            ),
            image_comparisons=tuple(
                replace(
                    recipe,
                    sources=tuple(s for s in recipe.sources if s.file_id in identities),
                )
                for recipe in session.image_comparisons
            ),
            audio_comparisons=tuple(
                replace(
                    recipe,
                    sources=tuple(s for s in recipe.sources if s.file_id in identities),
                )
                for recipe in session.audio_comparisons
            ),
            comparison_tab="Text corpora"
            if self.tab == ComparisonFamily.TEXT
            else self.tab.value,
        )

    def close(self) -> None:
        self.columns.close()
        self.catalog.close()
