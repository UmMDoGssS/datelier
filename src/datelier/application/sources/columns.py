"""Distinguish mapped payload identity from ordinary supporting table fields."""

from datelier.inspection.arrays import ArrayRecordMapping
from datelier.inspection.table import Inspection
from datelier.io.types import ArrayOptions


def record_mapping(
    inspection: Inspection | None, column: str | None
) -> ArrayRecordMapping | None:
    if inspection is None or not isinstance(inspection.imported.options, ArrayOptions):
        return None
    options = inspection.imported.options
    if options.mapping is not None and column not in (
        "record_index",
        options.mapping.member,
    ):
        return None
    return options.mapping_for(inspection.imported.array_catalog, column)
