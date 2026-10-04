"""Explicit record extraction of scalar XML fields without silent data loss."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO
from xml.etree import ElementTree as ET

import polars as pl

from datelier.import_records import records_to_table
from datelier.import_source import read_source
from datelier.import_types import ImportFormat, ImportResult, XmlOptions
from datelier.xml_records import RecordPath, selected_records, validate_xml_source
from datelier.xml_types import infer_xml_types


def _record(
    record: ET.Element, options: XmlOptions, number: int
) -> tuple[dict[str, str | None], int]:
    row: dict[str, str | None] = {}
    excluded_attributes = 0

    def scalar(text: str | None) -> str | None:
        if text is None:
            return None
        value = text.strip() if options.strip_text else text
        return None if value == "" or value in options.null_values else value

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
    return row, excluded_attributes


def load_xml(path: Path, options: XmlOptions | None = None) -> ImportResult:
    options = options or XmlOptions()

    def read(source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        validate_xml_source(source)
        header = source.read(512)
        # XML declarations may contain whitespace beyond the initial read.
        if re.match(rb"(?:\xef\xbb\xbf)?<\?xml\s", header):
            while b"?>" not in header:
                more = source.read(512)
                if not more:
                    break
                header += more
        source.seek(0)
        declaration = re.match(rb"(?:\xef\xbb\xbf)?<\?xml\s+([^?]*)\?>", header)
        encoding = (
            re.search(rb"encoding\s*=\s*['\"]([^'\"]+)['\"]", declaration[1])
            if declaration
            else None
        )
        if encoding and encoding[1].lower() not in (b"utf-8", b"utf8"):
            raise ValueError(
                "XML input must use UTF-8 encoding; "
                "convert the source before importing."
            )
        record_path = RecordPath(options)
        excluded: int = 0

        def records() -> Iterator[dict[str, str | None]]:
            nonlocal excluded
            found = False
            for number, record in enumerate(selected_records(source, record_path), 1):
                found = True
                row, skipped = _record(record, options, number)
                excluded += skipped
                yield row
            if not found:
                raise ValueError(
                    f"No XML records match {options.record_path!r}; "
                    "check the path and namespaces."
                )

        table = records_to_table(records(), as_text=True)
        if options.infer_types:
            table = infer_xml_types(table, dates=options.try_parse_dates)
        diagnostics = (
            f"XML record path {options.record_path!r}: "
            f"{table.height} records in document order.",
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
