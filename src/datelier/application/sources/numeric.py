"""Shared array/tensor metadata and explicit slice command interface."""

from dataclasses import dataclass
from typing import Protocol

from datelier.application.sources.mapping import RecordMappingDraft
from datelier.application.sources.slicing import SliceDraft
from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.arrays.slices import PreparedSlice
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.checkpoints.slices import PreparedTensorSlice
from datelier.inspection.checkpoints.types import CheckpointCatalog


class SliceJobs(Protocol):
    settings: SliceSettings

    @property
    def active(self) -> PreparedSlice | PreparedTensorSlice | None: ...

    message: str

    @property
    def busy(self) -> bool: ...
    def request(self, settings: SliceSettings) -> None: ...
    def abandon(self) -> None: ...
    def set_retention(self, limit: int) -> None: ...


@dataclass(frozen=True)
class MemberEntry:
    name: str
    shape: tuple[int, ...]
    dtype: str
    bytes: int
    diagnostic: str
    fields: tuple[str, ...] = ()


class NumericSourceController:
    def __init__(self, jobs: SliceJobs) -> None:
        self.jobs = jobs
        self.entries: tuple[MemberEntry, ...] = ()
        self._entries: dict[str, MemberEntry] = {}
        self.catalog: ArrayCatalog | CheckpointCatalog | None = None
        self.member_mode = True
        self.height = 260.0
        self.retention_mib = 256
        self.slice = SliceDraft()
        self.mapping: RecordMappingDraft | None = None
        self._slices: dict[str, SliceDraft] = {}
        self._mappings: dict[str, RecordMappingDraft] = {}
        self._catalog: ArrayCatalog | CheckpointCatalog | None = None

    @property
    def settings(self) -> SliceSettings:
        return self.jobs.settings

    @settings.setter
    def settings(self, value: SliceSettings) -> None:
        self.jobs.settings = value
        self.slice.bind(value)

    @property
    def entry(self) -> MemberEntry | None:
        return self._entries.get(self.settings.member)

    @property
    def prepared(self) -> PreparedSlice | None:
        value = self.jobs.active
        return value.view if isinstance(value, PreparedTensorSlice) else value

    @property
    def storage(self) -> PreparedSlice | None:
        value = self.jobs.active
        return value.storage if isinstance(value, PreparedTensorSlice) else None

    def sync(self, catalog: ArrayCatalog | CheckpointCatalog | None) -> None:
        if catalog is self._catalog:
            self.slice.bind(self.settings)
            return
        self.catalog = self._catalog = catalog
        self.entries = ()
        self._entries.clear()
        self._slices.clear()
        self._mappings.clear()
        self.mapping = None
        self.slice = SliceDraft()
        if isinstance(catalog, ArrayCatalog):
            self.entries = tuple(
                MemberEntry(
                    m.name,
                    m.shape,
                    str(m.dtype),
                    m.raw_bytes,
                    m.diagnostic,
                    m.dtype.names or () if m.dtype is not None else (),
                )
                for m in catalog.members
            )
            self.member_mode = catalog.aligned_first_dim is None
        elif catalog:
            self.entries = tuple(
                MemberEntry(m.name, m.shape, m.dtype, m.raw_bytes, m.diagnostic)
                for m in catalog.tensors
            )
        self._entries = {entry.name: entry for entry in self.entries}
        if self.entries:
            previous, member_mode = self.settings, self.member_mode
            name = (
                previous.member
                if previous.member in {m.name for m in self.entries}
                else self.entries[0].name
            )
            self.choose(name)
            if previous.member == name:
                self.settings = previous
            self.member_mode = member_mode

    def choose(self, name: str) -> None:
        entry = self._entries.get(name)
        if entry is None:
            raise ValueError("Selected member is unavailable")
        axes = tuple(range(max(0, len(entry.shape) - 2), len(entry.shape)))
        settings = SliceSettings(
            name,
            axes,
            (0,) * len(entry.shape),
            (0,) * len(axes),
            (128,) * len(axes),
            scalar=not axes,
        )
        if name in self._slices:
            self.slice = self._slices[name]
            settings = self.slice.bound or settings
        else:
            self.slice = self._slices[name] = SliceDraft()
        self.settings = settings
        self.member_mode = True
        self.mapping = None
        if (
            isinstance(self.catalog, ArrayCatalog)
            and entry.shape
            and not entry.diagnostic
        ):
            if name not in self._mappings:
                self._mappings[name] = RecordMappingDraft(self.catalog, name)
            self.mapping = self._mappings[name]

    def request(self) -> None:
        entry = self.entry
        if entry is None or entry.diagnostic:
            raise ValueError(
                entry.diagnostic if entry else "Choose an available member"
            )
        self.slice.bind(self.settings)
        settings = self.slice.build(entry.shape, entry.fields)
        self.jobs.set_retention(self.retention_mib * 1024 * 1024)
        self.jobs.request(settings)

    def capture_slice(self) -> SliceSettings:
        entry = self.entry
        if entry is None:
            return self.settings
        self.slice.bind(self.settings)
        return self.slice.build(entry.shape, entry.fields)
