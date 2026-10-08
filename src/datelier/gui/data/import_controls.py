"""Contextual dataset import settings rendered from prepared application state."""

from dataclasses import dataclass, field, fields
from pathlib import Path

from imgui_bundle import imgui

from datelier.io.csv import CsvOptions
from datelier.io.importing import detect_format
from datelier.io.types import (
    ArrayOptions,
    CheckpointOptions,
    ImportFormat,
    ImportOptions,
    JsonOptions,
    MediaOptions,
    ObjectOptions,
    ParquetOptions,
    XmlOptions,
)


@dataclass
class ImportControls:
    path: str = ""
    format_index: int = 0
    options_expanded: bool = False
    separator: str = ""
    quote: str = '"'
    header: bool = True
    text_only: bool = False
    dates: bool = False
    infer_rows: int = 100
    skip_rows: int = 0
    null_tokens: str = ""
    parquet_columns: str = ""
    xml_path: str = "./*"
    xml_namespaces: str = ""
    xml_attributes: bool = True
    xml_strip: bool = True
    media_lines: bool = False
    media_recursive: bool = True
    object_syntax: int = 0
    array_archive: int = 0
    array_header_bytes: int = 10_000
    array_record_table: bool = True
    checkpoint_nodes: int = 200_000
    checkpoint_depth: int = 128
    error: str = ""
    _bound: tuple[ImportFormat, ImportOptions, tuple[object, ...]] | None = field(
        default=None, repr=False
    )

    def _draft(self) -> tuple[object, ...]:
        return tuple(
            getattr(self, item.name)
            for item in fields(self)
            if item.name
            not in ("path", "format_index", "options_expanded", "error", "_bound")
        )

    def bind_settings(self, format: ImportFormat, options: ImportOptions) -> None:
        self.format_index = list(ImportFormat).index(format) + 1
        if isinstance(options, CsvOptions):
            self.separator, self.header = options.separator, options.has_header
            self.quote = options.quote_char or ""
            self.text_only, self.dates = (
                not options.infer_types,
                options.try_parse_dates,
            )
            self.infer_rows = options.infer_schema_length or 0
            self.skip_rows, self.null_tokens = (
                options.skip_rows,
                "|".join(options.null_values),
            )
        elif isinstance(options, JsonOptions):
            self.text_only = options.read_as_text
        elif isinstance(options, ParquetOptions):
            self.parquet_columns = "|".join(options.columns or ())
        elif isinstance(options, MediaOptions):
            self.media_lines, self.media_recursive = (
                options.text_lines,
                options.recursive,
            )
        elif isinstance(options, ArrayOptions):
            self.array_archive = (None, False, True).index(options.archive)
            self.array_header_bytes = options.max_header_bytes
            self.array_record_table = options.record_table
        elif isinstance(options, CheckpointOptions):
            self.checkpoint_nodes = options.max_nodes
            self.checkpoint_depth = options.max_depth
        elif isinstance(options, ObjectOptions):
            self.object_syntax = ("", "json", "toml").index(options.syntax)
            self.text_only = options.read_as_text
        else:
            self.xml_path = options.record_path
            self.xml_namespaces = "|".join(
                f"{key}={uri}" for key, uri in options.namespaces
            )
            self.xml_attributes, self.xml_strip = (
                options.include_attributes,
                options.strip_text,
            )
            self.text_only, self.dates = (
                not options.infer_types,
                options.try_parse_dates,
            )
            self.null_tokens = "|".join(options.null_values)
        # Retain literal | in names/tokens until the bound controls change.
        self._bound = format, options, self._draft()

    def selected_format(self) -> ImportFormat:
        return (
            detect_format(Path(self.path))
            if self.format_index == 0
            else list(ImportFormat)[self.format_index - 1]
        )

    def options(self, selected: ImportFormat) -> ImportOptions:
        if self._bound is not None and (selected, self._draft()) == (
            self._bound[0],
            self._bound[2],
        ):
            return self._bound[1]
        if selected == ImportFormat.ARRAY:
            return ArrayOptions(
                (None, False, True)[self.array_archive],
                self.array_header_bytes,
                record_table=self.array_record_table,
            )
        if selected == ImportFormat.CHECKPOINT:
            return CheckpointOptions(self.checkpoint_nodes, self.checkpoint_depth)
        if selected == ImportFormat.OBJECT:
            return ObjectOptions(
                syntax=("", "json", "toml")[self.object_syntax],
                read_as_text=self.text_only,
            )
        if selected == ImportFormat.MEDIA:
            return MediaOptions(
                text_lines=self.media_lines, recursive=self.media_recursive
            )
        if selected == ImportFormat.XML:
            namespaces: list[tuple[str, str]] = []
            for entry in self.xml_namespaces.split("|"):
                if entry:
                    prefix, separator, uri = entry.partition("=")
                    if not separator:
                        raise ValueError(
                            "Namespaces use prefix=URI entries separated by |."
                        )
                    namespaces.append((prefix, uri))
            return XmlOptions(
                record_path=self.xml_path,
                namespaces=tuple(namespaces),
                include_attributes=self.xml_attributes,
                strip_text=self.xml_strip,
                infer_types=not self.text_only,
                try_parse_dates=self.dates,
                null_values=tuple(self.null_tokens.split("|"))
                if self.null_tokens
                else (),
            )
        if selected == ImportFormat.PARQUET:
            return ParquetOptions(
                columns=tuple(self.parquet_columns.split("|"))
                if self.parquet_columns
                else None
            )
        if selected in (ImportFormat.JSON, ImportFormat.JSONL):
            return JsonOptions(read_as_text=self.text_only)
        return CsvOptions(
            separator=self.separator.replace("\\t", "\t")
            or ("\t" if selected == ImportFormat.TSV else ","),
            has_header=self.header,
            quote_char=self.quote or None,
            infer_types=not self.text_only,
            try_parse_dates=self.dates,
            infer_schema_length=None if self.infer_rows == 0 else self.infer_rows,
            skip_rows=self.skip_rows,
            null_values=tuple(self.null_tokens.split("|")) if self.null_tokens else (),
        )

    def show_options(self, selected: ImportFormat | None) -> None:
        if selected == ImportFormat.CHECKPOINT:
            _, self.checkpoint_nodes = imgui.input_int(
                "Maximum metadata nodes", self.checkpoint_nodes
            )
            _, self.checkpoint_depth = imgui.input_int(
                "Maximum metadata depth", self.checkpoint_depth
            )
            imgui.text_wrapped(
                "Optional CPU PyTorch inspection. Open nested metadata and tensor "
                "shapes first; prepare values explicitly."
            )
            return
        if selected == ImportFormat.ARRAY:
            _, self.array_archive = imgui.combo(
                "Array container", self.array_archive, ["Automatic", "NPY", "NPZ"]
            )
            _, self.array_header_bytes = imgui.input_int(
                "Maximum header bytes", self.array_header_bytes
            )
            _, self.array_record_table = imgui.checkbox(
                "Aligned NPZ members as record columns", self.array_record_table
            )
            imgui.text_wrapped(
                "Matching first dimensions open as records with scalar values and "
                "lazy array cells. Other sources open as member metadata."
            )
            return
        if selected is None:
            imgui.text_wrapped("Choose a format or enter a supported file extension.")
            return
        if selected == ImportFormat.OBJECT:
            _, self.object_syntax = imgui.combo(
                "Object syntax", self.object_syntax, ["Automatic", "JSON", "TOML"]
            )
            _, self.text_only = imgui.checkbox(
                "Read record columns as text", self.text_only
            )
            imgui.text_wrapped(
                "Keep the source hierarchy; open compatible record arrays "
                "as table views."
            )
            return
        if selected == ImportFormat.MEDIA:
            _, self.media_lines = imgui.checkbox(
                "Text: one record per line", self.media_lines
            )
            _, self.media_recursive = imgui.checkbox(
                "Include media subfolders", self.media_recursive
            )
            imgui.text_wrapped(
                "Default: one record per file, with lazy payload previews. "
                "Line records read text explicitly; sources remain unchanged."
            )
            if imgui.button("Refresh media manifest on reload"):
                self._bound = None
            return
        if selected == ImportFormat.XML:
            imgui.text_wrapped(
                "Record path is relative to the root. ./* selects root children; "
                ".//record selects descendants."
            )
            _, self.xml_path = imgui.input_text("Record path", self.xml_path)
            imgui.text_wrapped(
                "Namespaces: prefix=URI, separated by |. "
                "Qualified {URI} names also work in paths."
            )
            _, self.xml_namespaces = imgui.input_text("Namespaces", self.xml_namespaces)
            _, self.xml_attributes = imgui.checkbox(
                "Include attributes", self.xml_attributes
            )
            _, self.xml_strip = imgui.checkbox("Trim text whitespace", self.xml_strip)
            _, self.text_only = imgui.checkbox("Read columns as text", self.text_only)
            _, self.dates = imgui.checkbox("Parse ISO dates", self.dates)
            _, self.null_tokens = imgui.input_text("Null tokens (|)", self.null_tokens)
            imgui.text_wrapped(
                "Nested/repeated fields and mixed content are rejected. "
                "Missing/empty fields become null."
            )
            return
        if selected == ImportFormat.PARQUET:
            imgui.text_wrapped(
                "Stored types are preserved. Nested columns must be excluded "
                "or flattened before import."
            )
            _, self.parquet_columns = imgui.input_text(
                "Columns (|; empty = all)", self.parquet_columns
            )
            return
        _, self.text_only = imgui.checkbox("Read columns as text", self.text_only)
        if selected in (ImportFormat.JSON, ImportFormat.JSONL):
            imgui.text_wrapped(
                "Flat record objects only. Types use all records; "
                "missing fields become null. "
                "Nested objects/arrays are rejected with a field diagnostic."
            )
            return
        _, self.separator = imgui.input_text("Delimiter (\\t = tab)", self.separator)
        _, self.quote = imgui.input_text("Quote (empty = none)", self.quote)
        _, self.header = imgui.checkbox("First record is a header", self.header)
        _, self.dates = imgui.checkbox("Parse dates", self.dates)
        _, self.infer_rows = imgui.input_int("Infer rows (0 = all)", self.infer_rows)
        _, self.skip_rows = imgui.input_int("Skip records", self.skip_rows)
        _, self.null_tokens = imgui.input_text("Null tokens (|)", self.null_tokens)
