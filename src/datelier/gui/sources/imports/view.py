"""Source controls dispatch concrete forms through one explicit registry."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.imports import ImportController
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.fields import ChoiceField, TextField
from datelier.gui.components.native import target
from datelier.gui.components.routing import RoutedContent
from datelier.gui.sources.imports.media import MediaForm
from datelier.gui.sources.imports.structured import (
    ArrayForm,
    CheckpointForm,
    ObjectForm,
)
from datelier.gui.sources.imports.tabular import (
    DelimitedForm,
    JsonForm,
    ParquetForm,
    XmlForm,
)
from datelier.io.types import ImportFormat


class ImportSettings(Container):
    def __init__(
        self,
        model: ImportController,
        failed: Callable[[], bool],
        abandon: Callable[[], None],
    ) -> None:
        self.model, self.failed, self._was_failed = model, failed, False
        forms: dict[str, Component] = {
            ImportFormat.CSV: DelimitedForm(model.csv),
            ImportFormat.TSV: DelimitedForm(model.tsv),
            ImportFormat.JSON: JsonForm(model.json),
            ImportFormat.JSONL: JsonForm(model.jsonl),
            ImportFormat.PARQUET: ParquetForm(model.parquet),
            ImportFormat.XML: XmlForm(model.xml),
            ImportFormat.MEDIA: MediaForm(model.media),
            ImportFormat.OBJECT: ObjectForm(model.objects),
            ImportFormat.ARRAY: ArrayForm(model.arrays),
            ImportFormat.CHECKPOINT: CheckpointForm(model.checkpoints),
        }
        super().__init__(
            "import-settings",
            (
                TextField(
                    "path",
                    "Source path",
                    lambda: model.path,
                    lambda v: setattr(model, "path", v),
                ),
                ChoiceField(
                    "format",
                    "Import format",
                    (None, *ImportFormat),
                    lambda: model.format,
                    lambda v: setattr(model, "format", v),
                    ("Automatic", *(f.value for f in ImportFormat)),
                ),
                RoutedContent(
                    forms, lambda: model.selected.value if model.selected else ""
                ),
                CommandButton(
                    "import",
                    "Import / reload source",
                    model.request,
                    lambda: (
                        bool(model.path.strip())
                        and not model.busy
                        and not model.blocked
                    ),
                ),
                JobFeedback(
                    "load",
                    lambda: JobSnapshot(
                        "Loading source…" if model.busy else "", model.busy
                    ),
                    abandon,
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        if self.model.blocked:
            return
        failed = self.failed()
        if failed and not self._was_failed or not self.model.path:
            imgui.set_next_item_open(
                True, imgui.Cond_.always if failed else imgui.Cond_.once
            )
        self._was_failed = failed
        opened = imgui.collapsing_header("Import settings")
        target(frame, "toggle")
        if opened:
            super().render(frame)
