"""Delimited, JSON, Parquet and XML drafts validate only at explicit submission."""

from dataclasses import replace

from datelier.application.imports.base import OptionsDraft, entries, option
from datelier.io.types import (
    CsvOptions,
    ImportOptions,
    JsonOptions,
    ParquetOptions,
    XmlOptions,
)


class DelimitedDraft(OptionsDraft):
    def __init__(self, separator: str = ",") -> None:
        self.bind(CsvOptions(separator=separator))

    def bind(self, value: ImportOptions) -> None:
        self.base = option(value, CsvOptions)
        self.separator = self.base.separator.replace("\t", "\\t")
        self.quote = self.base.quote_char or ""
        self.header = self.base.has_header
        self.text_only = not self.base.infer_types
        self.dates = self.base.try_parse_dates
        self.infer_rows = self.base.infer_schema_length or 0
        self.skip_rows = self.base.skip_rows
        self.null_tokens = "\n".join(self.base.null_values)

    def build(self) -> CsvOptions:
        return replace(
            self.base,
            separator=self.separator.replace("\\t", "\t"),
            quote_char=self.quote or None,
            has_header=self.header,
            infer_types=not self.text_only,
            try_parse_dates=self.dates,
            infer_schema_length=self.infer_rows or None,
            skip_rows=self.skip_rows,
            null_values=entries(self.null_tokens, self.base.null_values),
        )


class JsonDraft(OptionsDraft):
    def __init__(self) -> None:
        self.bind(JsonOptions())

    def bind(self, value: ImportOptions) -> None:
        self.base = option(value, JsonOptions)
        self.text_only = self.base.read_as_text

    def build(self) -> JsonOptions:
        return replace(self.base, read_as_text=self.text_only)


class ParquetDraft(OptionsDraft):
    def __init__(self) -> None:
        self.bind(ParquetOptions())

    def bind(self, value: ImportOptions) -> None:
        self.base = option(value, ParquetOptions)
        self.columns = "\n".join(self.base.columns or ())

    def build(self) -> ParquetOptions:
        return replace(
            self.base, columns=entries(self.columns, self.base.columns or ()) or None
        )


class XmlDraft(OptionsDraft):
    def __init__(self) -> None:
        self.bind(XmlOptions())

    def bind(self, value: ImportOptions) -> None:
        self.base = option(value, XmlOptions)
        self.path = self.base.record_path
        self.namespaces = "\n".join(f"{key}={uri}" for key, uri in self.base.namespaces)
        self.attributes = self.base.include_attributes
        self.strip = self.base.strip_text
        self.text_only = not self.base.infer_types
        self.dates = self.base.try_parse_dates
        self.null_tokens = "\n".join(self.base.null_values)

    def build(self) -> XmlOptions:
        original = "\n".join(f"{key}={uri}" for key, uri in self.base.namespaces)
        namespaces = self.base.namespaces
        if self.namespaces != original:
            pairs: list[tuple[str, str]] = []
            for entry in self.namespaces.splitlines():
                if not entry:
                    continue
                key, separator, uri = entry.partition("=")
                if not separator:
                    raise ValueError("Namespaces use one prefix=URI entry per line")
                pairs.append((key, uri))
            namespaces = tuple(pairs)
        return replace(
            self.base,
            record_path=self.path,
            namespaces=namespaces,
            include_attributes=self.attributes,
            strip_text=self.strip,
            infer_types=not self.text_only,
            try_parse_dates=self.dates,
            null_values=entries(self.null_tokens, self.base.null_values),
        )
