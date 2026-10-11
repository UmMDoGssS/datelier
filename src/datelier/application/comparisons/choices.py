"""Shared metadata-only eligibility for reference fields and mapped media payloads."""

import polars as pl

from datelier.application.columns import ColumnChoice
from datelier.application.sources.columns import record_mapping
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.table import Inspection
from datelier.io.types import ArrayOptions


def media_choices(
    inspection: Inspection, columns: tuple[ColumnChoice, ...], layout: ArrayLayout
) -> tuple[ColumnChoice, ...]:
    options = inspection.imported.options
    mapping = options.mapping if isinstance(options, ArrayOptions) else None
    mapped = (
        (ColumnChoice(mapping.member, f"Mapped {layout.value}"),)
        if mapping and mapping.layout == layout
        else ()
    )
    schema = inspection.dataset.table.schema
    return mapped + tuple(
        ColumnChoice(
            c.name,
            c.group,
            enabled=schema[c.name] == pl.String
            or (
                (m := record_mapping(inspection, c.name)) is not None
                and m.layout == layout
            ),
            reason=f"Use a reference string or confirmed {layout.value} array mapping.",
        )
        for c in columns
        if c.name in schema
        and (not mapping or c.name not in (mapping.member, "record_index"))
    )
