"""Dataset import and schema controls rendered from prepared application state."""

from dataclasses import dataclass
from pathlib import Path

from imgui_bundle import imgui

from datelier.column_roles import allowed_roles
from datelier.editing import DatasetEditor
from datelier.import_csv import CsvOptions, ImportFailure
from datelier.import_types import (
    ImportFormat,
    ImportOptions,
    JsonOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.importing import detect_format
from datelier.loading import DatasetLoader, LoadPhase
from datelier.operations import SetColumnRole


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
    error: str = ""

    def selected_format(self) -> ImportFormat:
        return (
            detect_format(Path(self.path))
            if self.format_index == 0
            else list(ImportFormat)[self.format_index - 1]
        )

    def options(self, selected: ImportFormat) -> ImportOptions:
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
        if selected is None:
            imgui.text_wrapped("Choose a format or enter a supported file extension.")
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

    def show(self, loader: DatasetLoader) -> None:
        imgui.push_item_width(imgui.get_content_region_avail().x * 0.5)
        _, self.path = imgui.input_text("Path", self.path)
        _, self.format_index = imgui.combo(
            "Format",
            self.format_index,
            ["Auto", *[str(value) for value in ImportFormat]],
        )
        try:
            selected = self.selected_format()
        except ImportFailure:
            selected = None
        imgui.set_next_item_open(self.options_expanded, imgui.Cond_.always)
        self.options_expanded = imgui.collapsing_header("Import options")
        if self.options_expanded:
            self.show_options(selected)
        if imgui.button("Open dataset"):
            try:
                if not self.path.strip():
                    raise ValueError("Enter a dataset path.")
                selected = self.selected_format()
                loader.request(Path(self.path), self.options(selected), format=selected)
                self.error = ""
            except (ValueError, ImportFailure) as error:
                self.error = str(error)
        imgui.pop_item_width()
        if loader.status.phase == LoadPhase.LOADING:
            imgui.same_line()
            if imgui.button("Abandon load"):
                loader.abandon()
        imgui.separator()
        imgui.text_unformatted(loader.status.phase.value)
        if loader.status.path:
            imgui.text_wrapped(f"Requested source: {loader.status.path}")
        if loader.status.message:
            imgui.text_wrapped(loader.status.message)
        if self.error:
            imgui.text_wrapped(self.error)
        if loader.retired_running:
            imgui.text_wrapped(
                "An abandoned import is still finishing in the background."
            )
        if loader.active:
            inspection = loader.active
            imgui.separator()
            imgui.text_wrapped(f"Showing: {inspection.dataset.source.path}")
            imgui.text(
                f"{inspection.row_count:,} rows, {len(inspection.schema)} columns"
            )
            for message in inspection.imported.diagnostics:
                imgui.text_wrapped(message)


def show_schema(loader: DatasetLoader, editor: DatasetEditor) -> None:
    inspection = loader.active
    if inspection is None:
        imgui.text("Open a dataset to inspect its schema and missing values.")
        return
    dataset = inspection.dataset
    schema = dataset.table.schema
    imgui.text(f"Shape: ({inspection.row_count:,}, {len(inspection.schema):,})")
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.resizable
        | imgui.TableFlags_.sizing_stretch_prop
    )
    if imgui.begin_table("schema", 5, flags, imgui.ImVec2(-1, -1)):
        for name, weight in (
            ("Column", 1.0),
            ("Non nulls", 1.15),
            ("Uniques", 0.85),
            ("Type", 0.7),
            ("Interpretation", 1.9),
        ):
            imgui.table_setup_column(name, init_width_or_weight=weight)
        imgui.table_setup_scroll_freeze(0, 1)
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(inspection.schema))
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                summary = inspection.schema[index]
                info = dataset.role(summary.name)
                imgui.table_next_row()
                for column, text in enumerate(
                    (
                        summary.name,
                        f"{info.nonnull:,}",
                        f"{info.distinct:,}" if info.distinct is not None else "—",
                        summary.dtype,
                    )
                ):
                    imgui.table_set_column_index(column)
                    imgui.text_unformatted(text)
                imgui.table_set_column_index(4)
                options = (None, *allowed_roles(schema[summary.name]))
                labels = [
                    f"Auto: {info.inferred}".replace("Categorical", "Category").replace(
                        "Identifier", "ID"
                    ),
                    *[str(role) for role in options[1:]],
                ]
                imgui.set_next_item_width(-1)
                imgui.begin_disabled(editor.busy)
                changed, choice = imgui.combo(
                    f"##role {summary.name}", options.index(info.override), labels
                )
                imgui.end_disabled()
                if imgui.is_item_hovered():
                    imgui.set_tooltip(f"{info.role}. {info.reason}")
                if changed:
                    editor.request(SetColumnRole(summary.name, options[choice]))
        imgui.end_table()
