"""Flat record JSON/JSONL imports with validation before Polars conversion."""

import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, cast

import polars as pl

from datelier.io.json_records import array_records
from datelier.io.records import records_to_table
from datelier.io.source import read_source
from datelier.io.types import ImportFormat, ImportResult, JsonOptions

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


def decode_json(text: str) -> object:
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
        def records() -> Iterator[dict[str, JsonScalar]]:
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
        )
        if options.read_as_text:
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
