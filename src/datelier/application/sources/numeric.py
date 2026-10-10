"""Shared array/tensor metadata and explicit slice command interface."""

from dataclasses import dataclass, replace
from typing import Protocol

from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
    suggest_mapping,
)
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
        self.catalog: ArrayCatalog | CheckpointCatalog | None = None
        self.member_mode = True
        self.height = 260.0
        self.retention_mib = 256
        self.mapping = ArrayRecordMapping("$")
        self.mapping_reason = ""
        self.supporting: tuple[str, ...] = ()
        self.support_choices: tuple[str, ...] = ()
        self._catalog: ArrayCatalog | CheckpointCatalog | None = None

    @property
    def settings(self) -> SliceSettings:
        return self.jobs.settings

    @settings.setter
    def settings(self, value: SliceSettings) -> None:
        self.jobs.settings = value

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
            return
        self.catalog = self._catalog = catalog
        self.entries = ()
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
        entry = next((m for m in self.entries if m.name == name), None)
        if entry is None:
            raise ValueError("Selected member is unavailable")
        axes = tuple(range(max(0, len(entry.shape) - 2), len(entry.shape)))
        self.settings = SliceSettings(
            name,
            axes,
            (0,) * len(entry.shape),
            (0,) * len(axes),
            (128,) * len(axes),
            scalar=not axes,
        )
        self.member_mode = True
        if isinstance(self.catalog, ArrayCatalog) and entry.shape:
            suggestion = suggest_mapping(self.catalog, name)
            self.mapping, self.mapping_reason = suggestion.mapping, suggestion.reason
            self.support_choices = tuple(
                m.name
                for m in self.catalog.members
                if m.name != name and m.usable and len(m.shape) == 1
            )
            self.supporting = ()

    def request(self) -> None:
        self.jobs.request(self.settings)

    def confirmed_mapping(self) -> ArrayRecordMapping:
        catalog = self.catalog
        if not isinstance(catalog, ArrayCatalog):
            raise ValueError("Record mappings require an array source")
        mapping = replace(
            self.mapping,
            supporting=tuple(SupportingArray(name, name) for name in self.supporting),
        )
        mapping.record_count(catalog)
        return mapping

    def choose_layout(self, layout: ArrayLayout) -> None:
        self.mapping = replace(self.mapping, layout=layout)
