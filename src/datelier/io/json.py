"""Typed JSON/JSONL records with recursive validation before Polars conversion."""

import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, cast

import polars as pl

from datelier.io.json_records import array_records
from datelier.io.records import RecordValue, records_to_table
from datelier.io.source import read_source
from datelier.io.types import ImportFormat, ImportResult, JsonOptions


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field {key!r}; use unique field names.")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise ValueError(f"Nonstandard JSON value {value}; use null for missing values.")


def decode_json(text: str) -> object:
    # The standard JSON decoder is untyped; validation below narrows every value.
    return cast(
        object, json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    )


def _value(value: object, location: str) -> RecordValue:
    if isinstance(value, dict):
        return _record(value, location)
    if isinstance(value, list):
        return [_value(item, f"{location}[{i}]") for i, item in enumerate(value)]
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError(f"{location}: unsupported value.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{location}: number exceeds finite range.")
    return value


def _record(value: object, location: str) -> dict[str, RecordValue]:
    if not isinstance(value, dict):
        raise ValueError(f"{location}: expected an object containing named fields.")
    record: dict[str, RecordValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{location}: field names must be strings.")
        record[key] = _value(item, f"{location}, field {key!r}")
    return record


def load_json(
    path: Path, options: JsonOptions | None = None, *, lines: bool = False
) -> ImportResult:
    options = options or JsonOptions()
    format = ImportFormat.JSONL if lines else ImportFormat.JSON

    def read(source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        def records() -> Iterator[dict[str, RecordValue]]:
            if lines:
                for number, raw in enumerate(source, 1):
                    if not raw.strip():
                        continue
                    try:
                        yield _record(
                            decode_json(raw.decode("utf-8")), f"Line {number}"
                        )
                    except ValueError as error:
                        raise ValueError(f"Line {number}: {error}") from error
            else:
                for number, row in enumerate(
                    array_records(source, _object, _constant), 1
                ):
                    yield _record(row, f"Record {number}")

        table = records_to_table(records(), as_text=options.read_as_text)
        diagnostics = (
            "Types inferred across all records; missing fields become null.",
            "Nested objects/lists retain typed fields/elements; "
            "Inspect shows full values.",
        )
        if options.read_as_text:
            diagnostics += ("Columns loaded as text; JSON null remains null.",)
        return table, diagnostics

    return read_source(
        path,
        options,
        format,
        read,
        "Use record objects with compatible field and list-element types; "
        "for incompatible types read columns as text.",
    )
