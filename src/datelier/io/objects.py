"""Worker-side JSON/TOML hierarchy loading and explicit flat record extraction."""

import math
import tomllib
from dataclasses import replace
from datetime import date, datetime, time
from pathlib import Path
from typing import BinaryIO

import polars as pl

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.objects.types import (
    ObjectChild,
    ObjectNode,
    node_label,
)
from datelier.io.json import _decode
from datelier.io.records import ScalarValue, records_to_table
from datelier.io.source import read_source
from datelier.io.types import ImportFormat, ImportResult, ObjectOptions


def build_node(value: object, *, finite: bool = True) -> ObjectNode:
    if isinstance(value, dict):
        children: list[ObjectChild] = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Object keys must be strings")
            children.append(ObjectChild(key, build_node(item, finite=finite)))
        return ObjectNode("object", children=tuple(children))
    if isinstance(value, list):
        return ObjectNode(
            "array",
            children=tuple(
                ObjectChild(i, build_node(v, finite=finite))
                for i, v in enumerate(value)
            ),
        )
    if value is None or isinstance(
        value, (str, int, float, bool, date, datetime, time)
    ):
        if finite and isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Number exceeds finite range")
        return ObjectNode("null" if value is None else type(value).__name__, value)
    raise ValueError(f"Unsupported object value: {type(value).__name__}")


def extract_records(node: ObjectNode, *, as_text: bool = False) -> pl.DataFrame:
    if node.kind != "array":
        raise ValueError("Select an array of flat record objects to open a table view")
    rows: list[dict[str, ScalarValue]] = []
    for index, child in enumerate(node.children):
        if child.node.kind != "object":
            raise ValueError(f"Record {index}: expected an object with scalar fields")
        row: dict[str, ScalarValue] = {}
        for field in child.node.children:
            value = field.node.value
            if field.node.children or field.node.kind in ("object", "array"):
                raise ValueError(
                    f"Record {index}, field {field.key!r}: nested values cannot enter "
                    "a flat table. Select another record node in the object browser."
                )
            if isinstance(value, (date, datetime, time)):
                value = value.isoformat()
            if not isinstance(field.key, str):
                raise ValueError("Record fields must be named")
            row[field.key] = value
        rows.append(row)
    try:
        return records_to_table(rows, as_text=as_text)
    except (ValueError, pl.exceptions.PolarsError) as error:
        raise ValueError(
            f"Records cannot form a table: {error}. "
            "Try Read columns as text for mixed scalar types."
        ) from error


def load_object(path: Path, options: ObjectOptions | None = None) -> ImportResult:
    options = options or ObjectOptions()
    root: ObjectNode | None = None

    def read(source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        nonlocal root
        syntax = options.syntax or (
            "toml" if path.suffix.lower() == ".toml" else "json"
        )
        value = (
            tomllib.load(source)
            if syntax == "toml"
            else _decode(source.read().decode("utf8"))
        )
        root = build_node(value, finite=syntax == "json")
        if options.node_path is not None:
            table = extract_records(
                root.at(options.node_path), as_text=options.read_as_text
            )
            diagnostics = (
                f"Record view {node_label(options.node_path)}; "
                "source-row IDs are node indices.",
                "Temporal TOML scalars use lossless ISO text in table views.",
            )
        else:
            table = pl.DataFrame(
                {
                    "node": ["$"],
                    "type": [root.kind],
                    "preview": [root.preview],
                    "entries": [len(root.children)],
                }
            )
            diagnostics = (
                "Original hierarchy preserved; select a record array "
                "to open a named table view.",
            )
        return table, diagnostics

    result = read_source(
        path,
        options,
        ImportFormat.OBJECT,
        read,
        "Choose valid JSON/TOML or a compatible record array in the object browser.",
    )
    assert root is not None
    return replace(result, object_root=root)


def object_record_view(
    root: ObjectNode, source: SourceReference, options: ObjectOptions
) -> ImportResult:
    """Extract against already imported source data, without rereading its file."""
    if options.node_path is None:
        raise ValueError("A record view requires a selected node")
    table = extract_records(root.at(options.node_path), as_text=options.read_as_text)
    return ImportResult(
        Dataset.from_source(table, source),
        options,
        (
            f"Source node {node_label(options.node_path)}; "
            "source-row IDs are record indices.",
        ),
        ImportFormat.OBJECT,
        root,
    )
