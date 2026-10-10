"""Scoped image, collection and annotation preparation independent of rendering."""

from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.media_input import MediaController, MediaInput
from datelier.inspection.annotations.jobs import AnnotationJobs
from datelier.inspection.annotations.profile_jobs import AnnotationProfileJobs
from datelier.inspection.images.jobs import ImageJobs
from datelier.inspection.images.profile_jobs import ImageProfileJobs
from datelier.inspection.images.settings import ImageSettings
from datelier.inspection.images.types import ImageWindow
from datelier.io.types import ArrayOptions


class ImageController(MediaController):
    def __init__(self, executor: Executor | None = None) -> None:
        self._source: MediaInput | None = None
        self.jobs = ImageJobs(executor)
        self.settings = ImageSettings()
        self.profile_jobs = ImageProfileJobs(executor)
        self.annotations = AnnotationJobs(executor)
        self.annotation_profiles = AnnotationProfileJobs(executor)

    def sync(self, source: MediaInput) -> None:
        self._source = source
        active = source.active
        self.jobs.sync(
            source.file_id,
            source.view_name,
            active.dataset.revision if active else None,
            source.references,
            source.index,
        )
        self.jobs.cpu_bytes = min(self.settings.cpu_bytes, self.settings.gpu_bytes)
        self.jobs.set_retention(self.settings.disk_bytes)
        self.jobs.poll()
        self.profile_jobs.settings = self.settings.profile
        options = active.imported.options if active else None
        catalog = active.imported.array_catalog if active else None
        mapping = (
            options.mapping_for(catalog, self.settings.profile.column)
            if isinstance(options, ArrayOptions)
            else None
        )
        self.profile_jobs.bind(
            active.dataset if active else None,
            source.file_id,
            source.view_name,
            source.references,
            source.index,
            source.selected_rows,
            source.arrays,
            active.imported.array_catalog if active else None,
            mapping,
        )
        self.profile_jobs.poll()
        self.annotations.settings = self.settings.annotations
        self.annotations.bind(
            active.dataset if active else None,
            source.file_id,
            source.view_name,
            source.references,
            source.index,
            active.imported.array_catalog if active else None,
            options.mapping_for(catalog, source.inspect.primary)
            if isinstance(options, ArrayOptions)
            else None,
        )
        self.annotations.poll()
        if self.annotations.active is not None:
            self.settings = replace(
                self.settings, annotations=self.annotations.settings
            )
        self.annotation_profiles.bins = self.settings.annotation_view.bins
        self.annotation_profiles.bind(self.annotations.active)
        self.annotation_profiles.poll()

    def request_record(self, column: str, position: int) -> None:
        source = self._source
        active = source.active if source else None
        if active is None:
            return
        options = active.imported.options
        mapping = (
            options.mapping_for(active.imported.array_catalog, column)
            if isinstance(options, ArrayOptions)
            else None
        )
        self.jobs.request_record(
            active.dataset, column, position, active.imported.array_catalog, mapping
        )

    def request_window(self, window: ImageWindow) -> None:
        if self._source:
            self.jobs.request_window(window, self.settings.display, self._source.arrays)

    def close(self) -> None:
        self._source = None
        self.jobs.close()
        self.profile_jobs.close()
        self.annotations.close()
        self.annotation_profiles.close()
