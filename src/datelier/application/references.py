"""Source-scoped reference configuration and explicit ambiguity mappings."""

from dataclasses import dataclass, replace

from datelier.application.columns import ColumnChoice
from datelier.core.dataset import DatasetRevision
from datelier.inspection.references.jobs import ReferenceJobs
from datelier.inspection.references.types import (
    ReferenceMapping,
    ReferenceSettings,
    Resolution,
)


@dataclass(frozen=True)
class MappingTarget:
    column: str
    value: str
    revision: DatasetRevision
    resolution: Resolution


class ReferenceController:
    def __init__(self, jobs: ReferenceJobs) -> None:
        self.jobs = jobs
        self.thumbnails = True
        self.columns: tuple[ColumnChoice, ...] = ()
        self.roots, self.extensions = "", ""
        self.size, self.cpu_mib, self.gpu_mib = 128, 16, 8
        self.column: str | None = None
        self.value = self.path = ""
        self._settings: ReferenceSettings | None = None
        self.target: MappingTarget | None = None

    def sync(self, columns: tuple[ColumnChoice, ...]) -> None:
        if columns is not self.columns:
            self.columns = columns
            if self.column not in {c.name for c in columns}:
                self.column = next((c.name for c in columns), None)
        settings = self.jobs.settings
        if settings == self._settings:
            return
        self._settings = settings
        self.roots = "\n".join(settings.roots)
        self.extensions = ",".join(settings.extensions)
        self.size = settings.thumbnail_size
        self.cpu_mib, self.gpu_mib = (
            settings.cpu_bytes // 1048576,
            settings.gpu_bytes // 1048576,
        )

    def configure(self) -> None:
        if self.jobs.closed:
            raise ValueError("The reference source is closed")
        previous = self.jobs.settings
        roots = (
            previous.roots
            if self.roots == "\n".join(previous.roots)
            else tuple(r.strip() for r in self.roots.splitlines() if r.strip())
        )
        extensions = (
            previous.extensions
            if self.extensions == ",".join(previous.extensions)
            else tuple(
                e.strip().lower() for e in self.extensions.split(",") if e.strip()
            )
        )
        self.jobs.configure(
            replace(
                previous,
                roots=roots,
                extensions=extensions,
                thumbnail_size=self.size,
                cpu_bytes=self.cpu_mib * 1048576,
                gpu_bytes=self.gpu_mib * 1048576,
            )
        )

    def map(self, column: str, value: str, path: str) -> None:
        if (
            self.jobs.closed
            or column not in {c.name for c in self.columns}
            or not value
            or not path.strip()
        ):
            raise ValueError(
                "Choose a reference column, original cell value and exact file path"
            )
        settings = self.jobs.settings
        mappings = tuple(
            m for m in settings.mappings if (m.column, m.value) != (column, value)
        )
        self.jobs.configure(
            replace(
                settings, mappings=(*mappings, ReferenceMapping(column, value, path))
            )
        )

    def apply_mapping(self) -> None:
        if self.column is None:
            raise ValueError("Choose a reference column")
        self.map(self.column, self.value, self.path)

    def choose_target(self, column: str, value: str, resolution: Resolution) -> None:
        if self.jobs.revision is None:
            raise ValueError("Open a source before mapping a reference")
        self.target = MappingTarget(column, value, self.jobs.revision, resolution)
        self.path = ""

    def map_target(self, path: str) -> None:
        target = self.target
        if target is None or target.revision != self.jobs.revision:
            raise ValueError("The source rows changed; choose the reference again")
        self.map(target.column, target.value, path)

    def remove(self, mapping: ReferenceMapping) -> None:
        settings = self.jobs.settings
        self.jobs.configure(
            replace(
                settings, mappings=tuple(m for m in settings.mappings if m != mapping)
            )
        )
