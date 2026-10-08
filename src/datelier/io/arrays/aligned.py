"""First-axis NPZ records with scalar values and lazy array cell references."""

from dataclasses import replace

import polars as pl

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.io.arrays.records import _supporting_series
from datelier.io.arrays.storage import ArrayStore


def aligned_record_count(catalog: ArrayCatalog) -> int | None:
    return catalog.aligned_first_dim


def column_mapping(catalog: ArrayCatalog, column: str) -> ArrayRecordMapping | None:
    """Resolve an aligned cell using its column and stable source-row identity."""
    if aligned_record_count(catalog) is None or column not in catalog.indices:
        return None
    member = catalog.member(column)
    if len(member.shape) < 2:
        return None
    axes = tuple(range(1, len(member.shape)))
    layout = ArrayLayout.GENERIC
    channel = None
    if member.dtype is not None and member.dtype.kind in "biuf":
        if len(axes) == 2:
            layout = ArrayLayout.HEATMAP
        elif len(axes) == 3:
            channels = tuple(
                axis for axis in axes if member.shape[axis] in (1, 2, 3, 4)
            )
            if len(channels) == 1:
                channel = channels[0]
                layout = ArrayLayout.IMAGE
    return ArrayRecordMapping(
        column,
        layout=layout,
        display_axes=tuple(axis for axis in axes if axis != channel)[-2:],
        channel_axis=channel,
    )


def prepare_aligned_records(
    store: ArrayStore, catalog: ArrayCatalog
) -> tuple[Dataset, tuple[str, ...]]:
    count = aligned_record_count(catalog)
    if count is None:
        raise ValueError("NPZ members do not share a usable first dimension")
    columns: list[pl.Series] = []
    diagnostics = [
        f"{count} aligned records; columns are NPZ members, rows are original "
        "first-axis positions. Array cells reference original payloads lazily."
    ]
    diagnostics.extend(catalog.diagnostics)
    for member in catalog.members:
        if len(member.shape) == 1:
            with store.open_member(catalog, member.name) as array:
                series, diagnostic = _supporting_series(member.name, array)
            if diagnostic:
                diagnostics.append(f"{member.name}: {diagnostic}.")
        else:
            description = f"Array {member.shape[1:]} · {member.dtype}"
            series = pl.Series(
                member.name,
                [f"{description} · source record {row}" for row in range(count)],
                dtype=pl.String,
            )
        columns.append(series)
    dataset = Dataset.from_source(pl.DataFrame(columns), catalog.source)
    roles = []
    for info in dataset.roles or ():
        member = catalog.member(info.name)
        mapping = column_mapping(catalog, info.name)
        if mapping is not None:
            role = (
                ColumnRole.IMAGE
                if mapping.layout in (ArrayLayout.IMAGE, ArrayLayout.HEATMAP)
                else ColumnRole.IDENTIFIER
            )
            info = replace(
                info,
                inferred=role,
                reason=f"Per-record array {member.shape[1:]} · {member.dtype}; "
                "lazy first-axis reference, configurable through array records.",
            )
        elif dataset.table.schema[info.name].is_numeric():
            info = replace(
                info,
                inferred=ColumnRole.NUMERIC,
                reason=f"Scalar NPZ values retain original {member.dtype} numbers.",
            )
        roles.append(info)
    store.check_source(catalog)
    return replace(dataset, roles=tuple(roles)), tuple(diagnostics)
