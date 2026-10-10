"""Worker-side record selection and arbitrary supporting-column preparation."""

import json
from dataclasses import replace

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


def _supporting(field: RecordField) -> RecordField:
    if field.lines is None:
        return field
    return replace(
        field,
        text="{ ... }" if field.text.startswith("{") else "[ ... ]",
        lines=None,
    )


def prepare_records(
    dataset: Dataset, settings: InspectSettings, selection: tuple[int, ...] = ()
) -> RecordSet:
    settings.validate()
    names = dataset.table.columns
    requested = (
        *(settings.supporting or ()),
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
            (
                *(settings.supporting or ()),
                *((settings.primary,) if settings.primary else ()),
            )
        )
    )
    for slot in range(start, min(start + RECORD_PAGE_SIZE, len(records.positions))):
        position = int(records.positions[slot])
        fields: dict[str, RecordField] = {}
        for name in names:
            series = table.get_column(name)
            nested = series.dtype.is_nested()
            primary = name == settings.primary
            # Supporting containers use metadata only; complete payload conversion
            # is confined to the selected primary fields of this bounded page.
            if nested and not primary:
                is_null = bool(series.slice(position, 1).is_null().item())
                fields[name] = RecordField(
                    name,
                    "(null)"
                    if is_null
                    else "{ ... }"
                    if isinstance(series.dtype, pl.Struct)
                    else "[ ... ]",
                    is_null=is_null,
                )
                continue
            value = series[position]
            if isinstance(value, pl.Series):
                value = value.to_list()
            limit = 4096 if name == settings.primary else 256
            text = (
                json.dumps(value, ensure_ascii=False, indent=2, default=str)
                if nested and value is not None
                else "(null)"
                if value is None
                else str(value)
            )
            reference = (
                value
                if isinstance(value, str) and dataset.role(name).role in REFERENCE_ROLES
                else None
            )
            fields[name] = RecordField(
                name,
                text if nested else text[:limit],
                reference,
                value is None,
                not nested and len(text) > limit,
                tuple(text.splitlines()) if nested and value is not None else None,
            )
        cards.append(
            RecordCard(
                int(records.row_ids[slot]),
                position,
                fields.get(settings.primary or ""),
                tuple(_supporting(fields[n]) for n in settings.supporting or ()),
            )
        )
    return RecordPage(dataset.revision, start, tuple(cards))
