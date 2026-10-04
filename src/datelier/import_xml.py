"""Explicit record extraction of scalar XML fields without silent data loss."""

from pathlib import Path
from typing import BinaryIO
from xml.etree import ElementTree as ET

import polars as pl

from datelier.import_source import read_source
from datelier.import_types import ImportFormat, ImportResult, XmlOptions
from datelier.xml_types import infer_xml_types


def _records(
    root: ET.Element,
    options: XmlOptions,
) -> tuple[list[dict[str, str | None]], int]:
    try:
        selected = root.findall(options.record_path, dict(options.namespaces))
    except (SyntaxError, KeyError, TypeError) as error:
        raise ValueError(f"Invalid XML record path/namespaces: {error}") from error
    if not selected:
        raise ValueError(
            f"No XML records match {options.record_path!r}; "
            "check the path and namespaces."
        )
    rows: list[dict[str, str | None]] = []
    excluded_attributes = 0

    def scalar(text: str | None) -> str | None:
        if text is None:
            return None
        value = text.strip() if options.strip_text else text
        return None if value == "" or value in options.null_values else value

    for number, record in enumerate(selected, 1):
        row: dict[str, str | None] = {}
        if record.text and record.text.strip():
            raise ValueError(
                f"Record {number}: mixed or scalar record text is unsupported; "
                "select a record containing named fields."
            )
        for name, value in record.attrib.items():
            if options.include_attributes:
                row["@" + name] = scalar(value)
            else:
                excluded_attributes += 1
        for child in record:
            if len(child):
                raise ValueError(
                    f"Record {number}, field {child.tag!r}: nested XML is unsupported; "
                    "choose a deeper record path or flatten fields before importing."
                )
            if child.tag in row:
                raise ValueError(
                    f"Record {number}, field {child.tag!r}: "
                    "repeated fields are unsupported; "
                    "flatten repeated values before importing."
                )
            if child.tail and child.tail.strip():
                raise ValueError(
                    f"Record {number}, field {child.tag!r}: "
                    "mixed XML text is unsupported; "
                    "flatten fields before importing."
                )
            row[child.tag] = scalar(child.text)
            for name, value in child.attrib.items():
                if options.include_attributes:
                    row[child.tag + "/@" + name] = scalar(value)
                else:
                    excluded_attributes += 1
        rows.append(row)
    return rows, excluded_attributes


def load_xml(path: Path, options: XmlOptions | None = None) -> ImportResult:
    options = options or XmlOptions()

    def read(source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        text = source.read().decode("utf-8")
        if "<!DOCTYPE" in text or "<!ENTITY" in text:
            raise ValueError(
                "XML DTD/entity declarations are unsupported; supply plain tabular XML."
            )
        try:
            root = ET.fromstring(text)
        except ET.ParseError as error:
            raise ValueError(f"Malformed XML: {error}") from error
        rows, excluded = _records(root, options)
        fields = list(dict.fromkeys(name for row in rows for name in row))
        if not fields:
            raise ValueError(
                "Selected XML records have no fields; include attributes "
                "or select another record path."
            )
        table = pl.from_dicts(
            rows, schema={name: pl.String for name in fields}, strict=True
        )
        if options.infer_types:
            table = infer_xml_types(table, dates=options.try_parse_dates)
        diagnostics = (
            f"XML record path {options.record_path!r}: "
            f"{len(rows)} records in document order.",
            "Missing/empty fields become null. Namespaces retain {URI} names. "
            "Attributes map to @name and field/@name columns.",
            "Types inferred across all records."
            if options.infer_types
            else "Columns loaded as text.",
        )
        if excluded:
            diagnostics += (
                f"{excluded} attributes explicitly excluded by import settings.",
            )
        return table, diagnostics

    return read_source(
        path,
        options,
        ImportFormat.XML,
        read,
        "Check record extraction and namespaces; use scalar fields, "
        "or read as text for type conflicts.",
    )
