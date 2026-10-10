"""Scoped annotation links use stable row IDs and the shared record commands."""

from dataclasses import replace

from datelier.application.records import RecordController
from datelier.inspection.annotations.association_types import PreparedAnnotations
from datelier.inspection.records.types import RecordMode
from datelier.plotting.selection import SELECTION_LIMIT


def open_rows(
    records: RecordController,
    prepared: PreparedAnnotations,
    file_id: str,
    view_name: str,
    rows: tuple[int, ...],
) -> bool:
    if (prepared.file_id, prepared.view_name, prepared.revision) != (
        file_id,
        view_name,
        records.revision,
    ):
        return False
    records.selection.choose(prepared.revision, rows[:SELECTION_LIMIT])
    if len(rows) > SELECTION_LIMIT:
        records.selection.message = (
            f"{len(rows):,} matching image rows; selected the first "
            f"{SELECTION_LIMIT:,}. Narrow the class/source scope for other rows."
        )
    records.settings = replace(
        records.settings,
        mode=RecordMode.SELECTION,
        gallery=False,
        focus=0,
        primary=prepared.column,
        mapped_payload=None,
    )
    return True
