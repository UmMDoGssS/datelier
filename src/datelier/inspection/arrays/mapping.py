"""Confirmable record layouts, metadata suggestions and source-index locators."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from datelier.inspection.arrays.types import ArrayCatalog

if TYPE_CHECKING:
    from datelier.inspection.arrays.slices import SliceSettings


class ArrayLayout(StrEnum):
    GENERIC = "Generic array"
    IMAGE = "Image / grayscale"
    HEATMAP = "Numeric heatmap"
    AUDIO = "Waveform"


@dataclass(frozen=True)
class SupportingArray:
    member: str
    column: str
    record_axis: int = 0
    fixed: tuple[int, ...] = ()
    field: str | None = None

    def validate(self) -> None:
        if not self.member or not self.column or len(self.column) > 256:
            raise ValueError("Supporting arrays require a member and column name")
        if self.column == "record_index":
            raise ValueError("record_index is reserved for source provenance")
        if (
            self.record_axis < 0
            or len(self.fixed) > 64
            or any(i < 0 for i in self.fixed)
        ):
            raise ValueError("Supporting array coordinates must be nonnegative")


@dataclass(frozen=True)
class ArrayRecordMapping:
    member: str
    record_axis: int = 0
    layout: ArrayLayout = ArrayLayout.GENERIC
    display_axes: tuple[int, ...] = ()
    channel_axis: int | None = None
    fixed: tuple[int, ...] = ()
    supporting: tuple[SupportingArray, ...] = ()

    def validate(self) -> None:
        if not self.member or self.record_axis < 0:
            raise ValueError("Choose a member and nonnegative record axis")
        axes = (
            self.record_axis,
            *self.display_axes,
            *((self.channel_axis,) if self.channel_axis is not None else ()),
        )
        if (
            len(self.display_axes) > 2
            or len(set(axes)) != len(axes)
            or any(i < 0 for i in axes)
        ):
            raise ValueError(
                "Record, display and channel axes must be distinct and nonnegative"
            )
        if len(self.fixed) > 64 or any(i < 0 for i in self.fixed):
            raise ValueError("Fixed array coordinates must be nonnegative")
        if (
            self.layout in (ArrayLayout.IMAGE, ArrayLayout.HEATMAP)
            and len(self.display_axes) != 2
        ):
            raise ValueError("Image/heatmap layouts require two spatial display axes")
        if self.layout == ArrayLayout.AUDIO and len(self.display_axes) != 1:
            raise ValueError("Waveform layouts require one sample display axis")
        if len(self.supporting) > 256 or len(
            {s.column for s in self.supporting}
        ) != len(self.supporting):
            raise ValueError("Choose at most 256 distinct supporting columns")
        for support in self.supporting:
            support.validate()

    def record_count(self, catalog: ArrayCatalog) -> int:
        self.validate()
        member = catalog.member(self.member)
        if not member.usable:
            raise ValueError(member.diagnostic or "Array payload is unavailable")
        rank = len(member.shape)
        axes = (
            self.record_axis,
            *self.display_axes,
            *((self.channel_axis,) if self.channel_axis is not None else ()),
        )
        if any(axis >= rank for axis in axes):
            raise ValueError("Mapping axis is outside the selected array")
        fixed = self.fixed or (0,) * rank
        if len(fixed) != rank or any(
            position >= max(1, member.shape[i])
            for i, position in enumerate(fixed)
            if i not in axes
        ):
            raise ValueError("Fixed coordinates are outside the selected array")
        count = member.shape[self.record_axis]
        for support in self.supporting:
            supporting = catalog.member(support.member)
            if not supporting.usable:
                raise ValueError(
                    supporting.diagnostic or "Supporting dtype is unavailable"
                )
            if support.record_axis >= len(supporting.shape):
                raise ValueError(
                    f"{support.column}: supporting record axis is unavailable"
                )
            length = supporting.shape[support.record_axis]
            if length != count:
                raise ValueError(
                    f"{support.column}: {length} supporting records do not match "
                    f"{count} payload records; choose aligned arrays without truncation"
                )
            positions = support.fixed or (0,) * len(supporting.shape)
            if len(positions) != len(supporting.shape) or any(
                position >= max(1, supporting.shape[i])
                for i, position in enumerate(positions)
                if i != support.record_axis
            ):
                raise ValueError(
                    f"{support.column}: supporting coordinates are unavailable"
                )
        return count

    def slice_settings(
        self, catalog: ArrayCatalog, source_index: int, *, channel: int = 0
    ) -> SliceSettings:
        from datelier.inspection.arrays.slices import SliceSettings

        count = self.record_count(catalog)
        if not 0 <= source_index < count:
            raise ValueError("Record source index is outside the mapped array")
        shape = catalog.member(self.member).shape
        fixed = list(self.fixed or (0,) * len(shape))
        fixed[self.record_axis] = source_index
        if self.channel_axis is not None:
            if not 0 <= channel < shape[self.channel_axis]:
                raise ValueError("Channel is outside the mapped array")
            fixed[self.channel_axis] = channel
        axes = (
            self.display_axes
            or tuple(
                i
                for i in range(len(shape))
                if i not in (self.record_axis, self.channel_axis)
            )[-2:]
        )
        return SliceSettings(
            self.member,
            axes,
            tuple(fixed),
            (0,) * len(axes),
            (128,) * len(axes),
            scalar=not axes,
        )


@dataclass(frozen=True)
class MappingSuggestion:
    mapping: ArrayRecordMapping
    record_axes: tuple[int, ...]
    supporting_members: tuple[str, ...]
    reason: str


def suggest_mapping(catalog: ArrayCatalog, name: str) -> MappingSuggestion:
    member = catalog.member(name)
    shape = member.shape
    if not shape:
        raise ValueError("Scalar arrays do not define a record axis")
    scalar_arrays = tuple(
        m for m in catalog.members if m.name != name and m.usable and len(m.shape) == 1
    )
    matches = tuple(
        axis
        for axis, length in enumerate(shape)
        if any(m.shape[0] == length for m in scalar_arrays)
    )
    record_axis = matches[0] if matches else 0
    remaining = tuple(axis for axis in range(len(shape)) if axis != record_axis)
    channel: int | None = None
    layout = ArrayLayout.GENERIC
    if len(remaining) == 3:
        candidates = tuple(axis for axis in remaining if shape[axis] in (1, 3, 4))
        channel = candidates[-1] if len(candidates) == 1 else None
        if channel is not None:
            layout = ArrayLayout.IMAGE
    display = tuple(axis for axis in remaining if axis != channel)[-2:]
    if len(remaining) == 2:
        layout = ArrayLayout.HEATMAP
    elif len(remaining) == 1 and shape[remaining[0]] >= 64:
        layout = ArrayLayout.AUDIO
    supports = tuple(m.name for m in scalar_arrays if m.shape[0] == shape[record_axis])
    reason = (
        "Supporting scalar lengths match "
        + str(matches)
        + "; confirm the intended record axis."
        if matches
        else "No aligned scalar length identifies the record axis; "
        "axis 0 is a tentative default."
    )
    return MappingSuggestion(
        ArrayRecordMapping(name, record_axis, layout, display, channel),
        matches,
        supports,
        reason,
    )
