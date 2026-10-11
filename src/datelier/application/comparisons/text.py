"""Shared-tokenizer recipes and explicit corpus work, independent of rendering."""

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.comparisons.base import ComparisonFamily, RecipeController
from datelier.application.comparisons.catalog import SourceCatalog
from datelier.application.text_profiles import length_rows, statistic_rows
from datelier.inspection.text.comparisons.jobs import TextComparisonJobs
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
    TextComparisonViewSettings,
)
from datelier.inspection.text.comparisons.types import (
    PreparedTextComparison,
    TextComparisonInput,
)


class TextComparisonController(RecipeController[TextComparisonSettings]):
    def __init__(
        self, catalog: SourceCatalog, focus: Callable[[str], None], executor: Executor
    ) -> None:
        super().__init__(TextComparisonSettings())
        self.catalog, self.focus = catalog, focus
        self.jobs = TextComparisonJobs(executor)
        self.view = TextComparisonViewSettings()
        self.statistics: tuple[tuple[object, ...], ...] = ()
        self.lengths: tuple[tuple[object, ...], ...] = ()
        self._prepared: PreparedTextComparison | None = None

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.TEXT

    @property
    def active(self) -> PreparedTextComparison | None:
        return self.jobs.active

    def validate(self, recipe: TextComparisonSettings) -> None:
        recipe.validate()

    def mapping(self, identity: str) -> TextComparisonSource | None:
        return next((s for s in self.draft.sources if s.file_id == identity), None)

    def map_files(self, identities: tuple[str, ...]) -> None:
        previous = {s.file_id: s for s in self.draft.sources}
        sources = []
        for identity in identities:
            column = next(
                (c.name for c in self.catalog.text_choices(identity) if c.enabled), None
            )
            if identity in previous:
                sources.append(previous[identity])
            elif column:
                sources.append(TextComparisonSource(identity, column))
        self.draft = replace(self.draft, sources=tuple(sources))

    def update_mapping(self, source: TextComparisonSource) -> None:
        self.draft = replace(
            self.draft,
            sources=tuple(
                source if s.file_id == source.file_id else s for s in self.draft.sources
            ),
        )

    def prune(self, identities: set[str]) -> None:
        self.recipes = tuple(
            replace(r, sources=tuple(s for s in r.sources if s.file_id in identities))
            for r in self.recipes
        )
        self.draft = replace(
            self.draft,
            sources=tuple(s for s in self.draft.sources if s.file_id in identities),
        )

    def copy_tokenizer(self) -> None:
        source = self.catalog.by_id.get(self.catalog.current_id)
        if source is None:
            raise ValueError("Choose an available active file/view tokenizer")
        self.draft = replace(self.draft, tokens=source.text.tokens)

    def _bind(self) -> None:
        inputs = tuple(
            TextComparisonInput(
                mapping,
                source.dataset,
                source.title,
                source.references,
                source.index,
                source.selection,
                source.view_name,
            )
            for mapping in (self.recipe.sources if self.recipe else ())
            if (source := self.catalog.by_id.get(mapping.file_id)) and source.dataset
        )
        self.jobs.bind(self.recipe, inputs)

    def prepare(self) -> None:
        self.apply()
        self._bind()
        self.jobs.request()

    def sync(self) -> None:
        self._bind()
        self.jobs.poll()
        self.message = self.jobs.message
        selection = self.jobs.poll_selection(self.catalog.datasets)
        if selection:
            self.catalog.apply_selection(selection)
        prepared = self.active
        if prepared:
            self.view = replace(
                self.view,
                source=min(self.view.source, len(prepared.profiles) - 1),
                bin_index=min(self.view.bin_index, len(prepared.centers) - 1),
            )
        if prepared is self._prepared:
            return
        self._prepared = prepared
        self.statistics = self.lengths = ()
        if prepared:
            self.statistics = tuple(
                (label, p.settings.column, *row)
                for label, p in zip(prepared.labels, prepared.profiles, strict=True)
                for row in statistic_rows(p)
            )
            self.lengths = tuple(
                (label, *row)
                for label, p in zip(prepared.labels, prepared.profiles, strict=True)
                for row in length_rows(p)
            )

    def select(self, series: int, bin_index: int) -> None:
        result = self.active
        if (
            result is None
            or not 0 <= series < len(result.profiles)
            or not 0 <= bin_index < len(result.centers)
        ):
            raise ValueError("Choose a current text comparison source and length bin")
        identity = result.profiles[series].file_id
        source = self.catalog.by_id.get(identity)
        if source is None or source.dataset is None:
            raise ValueError("The contributing source closed or needs recovery")
        self.jobs.request_selection(result, series, bin_index, source.dataset)
        self.focus(identity)

    def abandon(self) -> None:
        self.jobs.clear()
        self.jobs.message = "Executing work is abandoned and cannot publish."

    def close(self) -> None:
        self.jobs.close()
        self.statistics = self.lengths = ()
        self._prepared = None
