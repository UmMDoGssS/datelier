"""Metadata-only record mapping drafts and configurable scalar support columns."""

from dataclasses import dataclass
from typing import cast

import numpy as np

from datelier.application.columns import ColumnChoice
from datelier.application.sources.slicing import indices
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
    suggest_mapping,
)
from datelier.inspection.arrays.types import ArrayCatalog


@dataclass
class SupportingDraft:
    key: str
    member: str
    column: str
    record_axis: int
    fixed: str
    fields: tuple[str, ...]
    shape: tuple[int, ...]
    field: str | None = None

    def build(self) -> SupportingArray:
        if self.field is not None and self.field not in self.fields:
            raise ValueError(f"{self.column}: selected structured field is unavailable")
        return SupportingArray(
            self.member, self.column, self.record_axis, indices(self.fixed), self.field
        )


class RecordMappingDraft:
    def __init__(self, catalog: ArrayCatalog, member: str) -> None:
        self.catalog = catalog
        suggestion = suggest_mapping(catalog, member)
        mapping = suggestion.mapping
        self.member, self.reason = member, suggestion.reason
        self.shape = catalog.member(member).shape
        self.record_axis, self.layout = mapping.record_axis, mapping.layout
        self.axes = ",".join(map(str, mapping.display_axes))
        self.channel = "" if mapping.channel_axis is None else str(mapping.channel_axis)
        self.fixed = ",".join("0" for _ in self.shape)
        self.supports: list[SupportingDraft] = []
        self.choices = tuple(
            ColumnChoice(
                item.name,
                "Array",
                reason=f"{item.shape} · {item.dtype}",
                label=item.name.replace("##", "# #"),
            )
            for item in catalog.members
            if item.usable and item.shape
        )
        self.candidate: tuple[str, ...] = ()
        self.page = 0
        self._sequence = 0

    def choose_layout(self, layout: ArrayLayout) -> None:
        if layout == self.layout:
            return
        self.layout = layout
        channel = self.channel_axis()
        remaining = tuple(
            axis
            for axis in range(len(self.shape))
            if axis not in (self.record_axis, channel)
        )
        count = 1 if layout == ArrayLayout.AUDIO else 2
        self.axes = ",".join(map(str, remaining[-count:]))

    def channel_axis(self) -> int | None:
        try:
            return int(self.channel) if self.channel.strip() else None
        except ValueError as error:
            raise ValueError("Channel axis must be an integer or empty") from error

    def add(self) -> SupportingDraft:
        if len(self.supports) >= 256 or not self.candidate:
            raise ValueError(
                "Choose a supporting member; at most 256 columns are allowed"
            )
        member = self.catalog.member(self.candidate[0])
        if not member.usable or not member.shape:
            raise ValueError("Supporting members require a usable record axis")
        existing = {support.column for support in self.supports} | {"record_index"}
        column = member.name
        suffix = 2
        while column in existing:
            column = f"{member.name}_{suffix}"
            suffix += 1
        self._sequence += 1
        support = SupportingDraft(
            str(self._sequence),
            member.name,
            column,
            0,
            ",".join("0" for _ in member.shape),
            member.dtype.names or () if member.dtype is not None else (),
            member.shape,
        )
        self.supports.append(support)
        self.page = (len(self.supports) - 1) // 8
        return support

    def remove(self, key: str) -> None:
        self.supports = [support for support in self.supports if support.key != key]
        self.page = min(self.page, max(0, (len(self.supports) - 1) // 8))

    def build(self) -> ArrayRecordMapping:
        result = ArrayRecordMapping(
            self.member,
            self.record_axis,
            self.layout,
            indices(self.axes),
            self.channel_axis(),
            indices(self.fixed),
            tuple(support.build() for support in self.supports),
        )
        result.record_count(self.catalog)
        for support in result.supporting:
            metadata = self.catalog.member(support.member)
            dtype = metadata.dtype
            if support.field is not None and dtype is not None:
                if cast(np.dtype[np.void], dtype)[support.field].subdtype is not None:
                    raise ValueError(
                        f"{support.column}: choose a scalar supporting field/coordinate"
                    )
        return result
