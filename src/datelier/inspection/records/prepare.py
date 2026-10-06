"""Worker-side record selection and arbitrary supporting-column preparation."""

import polars as pl

from datelier.core.column_roles import REFERENCE_ROLES
from datelier.core.dataset import Dataset
from datelier.inspection.records.types import (
    InspectSettings,
    RecordCard,
    RecordField,
    RecordMode,
    RecordPage,
    RecordSet,
)

RECORD_PAGE_SIZE = 4


def prepare_records(
    dataset: Dataset, settings: InspectSettings, selection: tuple[int, ...] = ()
) -> RecordSet:
    settings.validate()
    names = dataset.table.columns
    requested = (
        *settings.supporting,
        *((settings.primary,) if settings.primary else ()),
    )
    missing = tuple(n for n in requested if n not in names)
    if missing:
        raise ValueError(f"Inspect columns unavailable: {missing}")
    ids = dataset.row_ids
    if settings.mode == RecordMode.RANGE:
        start = min(settings.start - 1, len(ids))
        positions = pl.int_range(
            start, min(start + settings.count, len(ids)), eager=True
        )
    else:
        chosen = (
            ids.sort()
            .sample(n=min(settings.count, len(ids)), seed=settings.seed)
            .sort()
            if settings.mode == RecordMode.RANDOM
            else pl.Series(selection, dtype=pl.UInt64)
        )
        positions = ids.is_in(chosen.implode()).arg_true()
    return RecordSet(
        dataset.revision, settings, positions, ids.gather(positions), len(ids)
    )


def prepare_record_page(dataset: Dataset, records: RecordSet, start: int) -> RecordPage:
    if dataset.revision != records.revision:
        raise ValueError("Record collection belongs to another dataset revision")
    if start < 0:
        raise ValueError("Record page offset must be nonnegative")
    settings = records.settings
    table = dataset.table
    cards: list[RecordCard] = []
    names = tuple(
        dict.fromkeys(
            (*settings.supporting, *((settings.primary,) if settings.primary else ()))
        )
    )
    for slot in range(start, min(start + RECORD_PAGE_SIZE, len(records.positions))):
        position = int(records.positions[slot])
        fields: dict[str, RecordField] = {}
        for name in names:
            value = table.get_column(name)[position]
            limit = 4096 if name == settings.primary else 256
            text = "(null)" if value is None else str(value)
            reference = (
                value
                if isinstance(value, str) and dataset.role(name).role in REFERENCE_ROLES
                else None
            )
            fields[name] = RecordField(
                name, text[:limit], reference, value is None, len(text) > limit
            )
        cards.append(
            RecordCard(
                int(records.row_ids[slot]),
                position,
                fields.get(settings.primary or ""),
                tuple(fields[n] for n in settings.supporting),
            )
        )
    return RecordPage(dataset.revision, start, tuple(cards))
