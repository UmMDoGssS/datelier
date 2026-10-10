"""Narrow annotation commands and presentation metadata; no native dependencies."""

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.columns import ColumnChoice
from datelier.application.media_input import MediaInput
from datelier.application.sources.columns import record_mapping
from datelier.inspection.annotations.association_types import (
    AssociatedBox,
    AssociatedSource,
    PreparedAnnotations,
)
from datelier.inspection.annotations.jobs import AnnotationJobs
from datelier.inspection.annotations.overlay import OverlayClass
from datelier.inspection.annotations.profile_jobs import AnnotationProfileJobs
from datelier.inspection.annotations.profile_types import AnnotationProfile
from datelier.inspection.annotations.scene_jobs import SceneJobs
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
)
from datelier.inspection.annotations.view_settings import AnnotationViewSettings
from datelier.inspection.images.profile_types import ImageHistogram
from datelier.inspection.table import Inspection


class AnnotationController:
    def __init__(
        self,
        read_settings: Callable[[], AnnotationSettings],
        write_settings: Callable[[AnnotationSettings], None],
        read_view: Callable[[], AnnotationViewSettings],
        write_view: Callable[[AnnotationViewSettings], None],
        executor: Executor | None,
    ) -> None:
        self.read_settings, self.write_settings = read_settings, write_settings
        self.read_view, self.write_view = read_view, write_view
        self.jobs, self.profiles = (
            AnnotationJobs(executor),
            AnnotationProfileJobs(executor),
        )
        self.scene = SceneJobs(executor)
        self.selected: AssociatedBox | None = None
        self.columns: tuple[ColumnChoice, ...] = ()
        self.source_choices: tuple[ColumnChoice, ...] = ()
        self.class_choices: tuple[ColumnChoice, ...] = ()
        self._classes: dict[str, OverlayClass] = {}
        self._source: MediaInput | None = None
        self._prepared: PreparedAnnotations | None = None
        self._column_inspection: Inspection | None = None

    @property
    def source(self) -> AssociatedSource | None:
        prepared = self.jobs.active
        return (
            next(
                (
                    s
                    for s in prepared.sources
                    if s.recipe.id == self.read_view().source_id
                ),
                next(iter(prepared.sources), None),
            )
            if prepared
            else None
        )

    @property
    def profile(self) -> AnnotationProfile | None:
        source, prepared = self.source, self.profiles.active
        return (
            next(
                (
                    s
                    for s in prepared.sources
                    if source and s.source_id == source.recipe.id
                ),
                None,
            )
            if prepared
            else None
        )

    def sync(self, source: MediaInput) -> None:
        self._source = source
        self._bind()
        self.jobs.poll()
        if self.jobs.active is not None:
            self.write_settings(self.jobs.settings)
        self.profiles.bins = self.read_view().bins
        self.profiles.bind(self.jobs.active)
        self.profiles.poll()
        self.scene.bind(self.jobs.active)
        self.scene.poll()
        if self.jobs.active is not self._prepared:
            self._prepared = self.jobs.active
            self.selected = None
            self._classes = {}
            prepared = self.jobs.active
            self.source_choices = (
                tuple(
                    ColumnChoice(
                        s.recipe.id,
                        s.recipe.format.value,
                        label=s.recipe.name or s.recipe.id,
                    )
                    for s in prepared.sources
                )
                if prepared
                else ()
            )
            choices = []
            if prepared:
                for source_id, classes in prepared.overlay_classes.items():
                    for index, item in enumerate(classes):
                        key = f"{source_id}:{index}"
                        self._classes[key] = OverlayClass(source_id, item.id)
                        choices.append(
                            ColumnChoice(
                                key, source_id, label=f"{item.name} ({item.id})"
                            )
                        )
            self.class_choices = tuple(choices)
        active = source.active
        if active is not self._column_inspection:
            self._column_inspection = active
            self.columns = (
                tuple(ColumnChoice(name) for name in active.dataset.table.columns)
                if active
                else ()
            )
            mapping = record_mapping(active, "record_index")
            if mapping and not any(c.name == mapping.member for c in self.columns):
                self.columns = (
                    *self.columns,
                    ColumnChoice(mapping.member, "Mapped payload"),
                )

    def _bind(self) -> None:
        source = self._source
        if source is None:
            return
        active = source.active
        self.jobs.settings = self.read_settings()
        self.jobs.bind(
            active.dataset if active else None,
            source.file_id,
            source.view_name,
            source.references,
            source.index,
            active.imported.array_catalog if active else None,
            record_mapping(active, self.jobs.settings.column),
        )

    def request(self, column: str) -> None:
        source = self._source
        mapping = record_mapping(source.active, column) if source else None
        self.write_settings(
            replace(self.read_settings(), column=mapping.member if mapping else column)
        )
        self._bind()
        self.jobs.request()

    def request_profiles(self) -> None:
        self.profiles.bins = self.read_view().bins
        self.profiles.bind(self.jobs.active)
        self.profiles.request()

    def apply_source(self, source: AnnotationSource) -> None:
        source.validate()
        settings = self.read_settings()
        sources = tuple(source if s.id == source.id else s for s in settings.sources)
        if not any(s.id == source.id for s in sources):
            sources = (*sources, source)
        self.write_settings(replace(settings, sources=sources))
        self.write_view(replace(self.read_view(), source_id=source.id))

    def remove_source(self, identity: str) -> None:
        self.write_settings(
            replace(
                self.read_settings(),
                sources=tuple(
                    s for s in self.read_settings().sources if s.id != identity
                ),
            )
        )

    def class_selection(self) -> tuple[str, ...]:
        chosen = self.read_view().overlay.classes
        return tuple(
            key
            for key, item in self._classes.items()
            if chosen is None or item in chosen
        )

    def choose_classes(self, keys: tuple[str, ...]) -> None:
        view = self.read_view()
        self.write_view(
            replace(
                view,
                overlay=replace(
                    view.overlay, classes=tuple(self._classes[key] for key in keys)
                ),
            )
        )

    def distributions(self) -> tuple[ImageHistogram, ...]:
        profile = self.profile
        return (
            tuple(
                chart
                for chart in profile.distributions
                if chart.label == self.read_view().distribution
            )
            if profile
            else ()
        )

    def abandon(self) -> None:
        self.jobs.abandon()
        self.jobs.message = "Association abandoned; executing reads cannot publish."

    def abandon_profiles(self) -> None:
        self.profiles.abandon()
        self.profiles.message = (
            "Annotation profiling abandoned; executing work cannot publish."
        )

    def close(self) -> None:
        self.jobs.close()
        self.profiles.close()
        self.scene.close()
        self._source = self._prepared = self.selected = None
        self._column_inspection = None
        self.columns = self.source_choices = self.class_choices = ()
        self._classes.clear()
