"""Flat record JSON/JSONL imports with validation before Polars conversion."""

import json
import math
from pathlib import Path
from typing import BinaryIO, cast

import polars as pl

from datelier.import_source import read_source
from datelier.import_types import ImportFormat, ImportResult, JsonOptions

type JsonScalar = str | int | float | bool | None


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field {key!r}; use unique field names.")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise ValueError(f"Nonstandard JSON value {value}; use null for missing values.")


def _decode(text: str) -> object:
    # The standard JSON decoder is untyped; validation below narrows every value.
    return cast(
        object, json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    )


def _record(value: object, location: str) -> dict[str, JsonScalar]:
    if not isinstance(value, dict):
        raise ValueError(
            f"{location}: expected an object containing named scalar fields."
        )
    record: dict[str, JsonScalar] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{location}: field names must be strings.")
        if isinstance(item, (dict, list)):
            raise ValueError(
                f"{location}, field {key!r}: nested JSON is unsupported; "
                "flatten objects and arrays into scalar columns before importing."
            )
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"{location}, field {key!r}: unsupported value.")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError(f"{location}, field {key!r}: number exceeds finite range.")
        record[key] = item
    return record


def load_json(
    path: Path, options: JsonOptions | None = None, *, lines: bool = False
) -> ImportResult:
    options = options or JsonOptions()
    format = ImportFormat.JSONL if lines else ImportFormat.JSON

    def read(source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        records: list[dict[str, JsonScalar]] = []
        if lines:
            for number, raw in enumerate(source, 1):
                if not raw.strip():
                    continue
                try:
                    records.append(
                        _record(_decode(raw.decode("utf-8")), f"Line {number}")
                    )
                except ValueError as error:
                    raise ValueError(f"Line {number}: {error}") from error
        else:
            value = _decode(source.read().decode("utf-8"))
            if not isinstance(value, list):
                raise ValueError(
                    "Expected a JSON array of record objects; "
                    "use JSONL for one object per line."
                )
            records = [
                _record(row, f"Record {number}") for number, row in enumerate(value, 1)
            ]
        if not records or not any(records):
            raise ValueError(
                "No records with fields found; empty JSON has no tabular schema."
            )
        if options.read_as_text:
            records = [
                {
                    key: item
                    if isinstance(item, str) or item is None
                    else json.dumps(item)
                    for key, item in row.items()
                }
                for row in records
            ]
        # Scan all validated records so late keys/types cannot disappear.
        table = pl.from_dicts(records, infer_schema_length=None, strict=True)
        diagnostics = (
            "Types inferred across all records; missing fields become null.",
        )
        if options.read_as_text:
            table = table.cast(pl.String)
            diagnostics += ("Columns loaded as text; JSON null remains null.",)
        return table, diagnostics

    return read_source(
        path,
        options,
        format,
        read,
        "Use flat record objects with consistent scalar types; "
        "for mixed types read as text.",
    )
