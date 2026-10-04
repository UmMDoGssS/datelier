"""CSV import and schema controls rendered from prepared application state."""

from dataclasses import dataclass
from pathlib import Path

from imgui_bundle import imgui

from datelier.import_csv import CsvOptions
from datelier.loading import DatasetLoader, LoadPhase


@dataclass
class ImportControls:
    path: str = ""
    separator: str = ","
    quote: str = '"'
    header: bool = True
    text_only: bool = False
    dates: bool = False
    infer_rows: int = 100
    skip_rows: int = 0
    null_tokens: str = ""
    error: str = ""

    def show(self, loader: DatasetLoader) -> None:
        _, self.path = imgui.input_text("CSV path", self.path)
        if imgui.collapsing_header("Import options"):
            _, self.separator = imgui.input_text(
                "Delimiter (\\t for tab)", self.separator
            )
            _, self.quote = imgui.input_text("Quote (empty to disable)", self.quote)
            _, self.header = imgui.checkbox("First record is a header", self.header)
            _, self.text_only = imgui.checkbox("Read columns as text", self.text_only)
            _, self.dates = imgui.checkbox("Parse dates", self.dates)
            _, self.infer_rows = imgui.input_int(
                "Infer rows (0 = all)", self.infer_rows
            )
            _, self.skip_rows = imgui.input_int("Skip records", self.skip_rows)
            _, self.null_tokens = imgui.input_text(
                "Null tokens (separate with |)", self.null_tokens
            )
        if imgui.button("Open CSV"):
            try:
                if not self.path.strip():
                    raise ValueError("Enter a CSV path.")
                options = CsvOptions(
                    separator=self.separator.replace("\\t", "\t"),
                    has_header=self.header,
                    quote_char=self.quote or None,
                    infer_types=not self.text_only,
                    try_parse_dates=self.dates,
                    infer_schema_length=None
                    if self.infer_rows == 0
                    else self.infer_rows,
                    skip_rows=self.skip_rows,
                    null_values=tuple(self.null_tokens.split("|"))
                    if self.null_tokens
                    else (),
                )
                loader.request(Path(self.path), options)
                self.error = ""
            except ValueError as error:
                self.error = str(error)
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


def show_schema(loader: DatasetLoader) -> None:
    inspection = loader.active
    if inspection is None:
        imgui.text("Open a CSV to inspect its schema and missing values.")
        return
    imgui.text("Null counts cover every imported row.")
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.resizable
    )
    if imgui.begin_table("schema", 3, flags, imgui.ImVec2(-1, -1)):
        for name in ("Column", "Type", "Nulls"):
            imgui.table_setup_column(name)
        imgui.table_setup_scroll_freeze(0, 1)
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(inspection.schema))
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                summary = inspection.schema[index]
                imgui.table_next_row()
                for column, text in enumerate(
                    (summary.name, summary.dtype, f"{summary.null_count:,}")
                ):
                    imgui.table_set_column_index(column)
                    imgui.text_unformatted(text)
        imgui.end_table()
