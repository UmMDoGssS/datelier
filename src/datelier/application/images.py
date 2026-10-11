"""Scoped image, collection and annotation preparation independent of rendering."""

from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.annotations.controller import AnnotationController
from datelier.application.media_input import MediaController, MediaInput
from datelier.application.sources.columns import record_mapping
from datelier.inspection.images.jobs import ImageJobs
from datelier.inspection.images.profiles import ChannelSummary, ImageProfile
from datelier.inspection.images.profiles.jobs import ImageProfileJobs
from datelier.inspection.images.settings import ImageSettings
from datelier.inspection.images.types import ImageWindow


class ImageController(MediaController):
    def __init__(self, executor: Executor | None = None) -> None:
        self._source: MediaInput | None = None
        self.jobs = ImageJobs(executor)
        self.settings = ImageSettings()
        self.profile_jobs = ImageProfileJobs(executor)
        self.annotation_tools = AnnotationController(
            lambda: self.settings.annotations,
            lambda value: setattr(
                self, "settings", replace(self.settings, annotations=value)
            ),
            lambda: self.settings.annotation_view,
            lambda value: setattr(
                self, "settings", replace(self.settings, annotation_view=value)
            ),
            executor,
        )
        self.annotations = self.annotation_tools.jobs
        self.annotation_profiles = self.annotation_tools.profiles
        self.statistics: tuple[tuple[object, ...], ...] = ()
        self.channel_groups: tuple[tuple[str, str], ...] = ()
        self._profile: ImageProfile | None = None

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
        self._bind_profile(source)
        self.profile_jobs.poll()
        self._prepare_profile()
        self.annotation_tools.sync(source)

    def request_record(self, column: str, position: int) -> None:
        source = self._source
        active = source.active if source else None
        if active is None:
            return
        mapping = record_mapping(active, column)
        self.jobs.request_record(
            active.dataset, column, position, active.imported.array_catalog, mapping
        )

    def request_window(self, window: ImageWindow) -> None:
        if self._source:
            self.jobs.request_window(window, self.settings.display, self._source.arrays)

    @property
    def annotation_column(self) -> str:
        return (
            self.settings.annotations.column
            or (self._source.inspect.primary if self._source else None)
            or ""
        )

    def request_collection(self, column: str) -> None:
        source = self._source
        if source is None or source.active is None:
            raise ValueError("Open image records before preparing statistics")
        mapping = record_mapping(source.active, column)
        self.settings = replace(
            self.settings,
            profile=replace(
                self.settings.profile, column=mapping.member if mapping else column
            ),
        )
        self._bind_profile(source)
        self.profile_jobs.request()

    def _bind_profile(self, source: MediaInput) -> None:
        active = source.active
        self.profile_jobs.settings = self.settings.profile
        self.profile_jobs.bind(
            active.dataset if active else None,
            source.file_id,
            source.view_name,
            source.references,
            source.index,
            source.selected_rows,
            source.arrays,
            active.imported.array_catalog if active else None,
            record_mapping(active, self.settings.profile.column),
        )

    def abandon_profile(self) -> None:
        self.profile_jobs.abandon()
        self.profile_jobs.message = (
            "Image profiling abandoned; executing work cannot publish."
        )

    def _prepare_profile(self) -> None:
        profile = self.profile_jobs.active
        if profile is self._profile:
            return
        self._profile = profile
        self.statistics = (
            tuple(
                summary_row(s)
                for s in (*profile.dimension_summaries, *profile.summaries)
            )
            if profile
            else ()
        )
        self.channel_groups = (
            tuple(dict.fromkeys((s.key.mode, s.key.dtype) for s in profile.summaries))
            if profile
            else ()
        )

    @property
    def fixed_axes(self) -> tuple[tuple[int, int], ...]:
        prepared = self.jobs.metadata
        locator = prepared[0] if prepared else None
        if (
            locator is None
            or locator.catalog is None
            or locator.mapping is None
            or prepared is None
            or prepared[1].mode != "Numeric"
        ):
            return ()
        mapping = locator.mapping
        used = (mapping.record_axis, *mapping.display_axes, mapping.channel_axis)
        return tuple(
            (axis, length)
            for axis, length in enumerate(locator.catalog.member(mapping.member).shape)
            if axis not in used
        )

    def fixed_coordinate(self, axis: int) -> int:
        prepared = self.jobs.metadata
        mapping = prepared[0].mapping if prepared else None
        fixed = self.settings.display.fixed or (mapping.fixed if mapping else ())
        return fixed[axis] if axis < len(fixed) else 0

    def set_fixed_coordinate(self, axis: int, value: int) -> None:
        prepared = self.jobs.metadata
        locator = prepared[0] if prepared else None
        if locator is None or locator.catalog is None or locator.mapping is None:
            return
        mapping = locator.mapping
        shape = locator.catalog.member(mapping.member).shape
        fixed = list(self.settings.display.fixed or mapping.fixed or (0,) * len(shape))
        fixed[axis] = value
        self.settings = replace(
            self.settings, display=replace(self.settings.display, fixed=tuple(fixed))
        )

    def close(self) -> None:
        self._source = None
        self.jobs.close()
        self.profile_jobs.close()
        self.annotation_tools.close()
        self._profile = None
        self.statistics = self.channel_groups = ()


def summary_row(summary: ChannelSummary) -> tuple[object, ...]:
    return (
        summary.key.label,
        summary.values,
        summary.finite,
        summary.nonfinite,
        summary.minimum,
        summary.maximum,
        summary.mean,
        summary.stddev,
    )
