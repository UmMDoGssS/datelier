"""Association and profile tabs render bounded prepared annotation records."""

from collections.abc import Callable
from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.annotations.controller import AnnotationController
from datelier.application.columns import SingleSelection
from datelier.gui.annotations.profiles import AnnotationProfileContent
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.tables import SequenceTable
from datelier.gui.shell.navigation import CanvasTabs, NamedTab
from datelier.inspection.annotations.association import AssociatedBox


class AssociationContent(Container):
    def __init__(
        self,
        model: AnnotationController,
        open_rows: Callable[[tuple[int, ...]], None],
        select: Callable[[AssociatedBox], None],
    ) -> None:
        self.model, self.open_rows, self.select = model, open_rows, select
        super().__init__(
            "associations",
            (
                SequenceTable(
                    "images",
                    (
                        "Image key",
                        "Status / labels",
                        "Candidate rows",
                        "Image reference",
                        "Original size",
                        "Diagnostics",
                    ),
                    lambda: model.source.images if model.source else (),
                    lambda item: (
                        item.image.key,
                        f"{item.status} / {item.image.label_status}",
                        str(item.candidates[:128])
                        + (
                            "… (128 candidates shown)"
                            if len(item.candidates) > 128
                            else ""
                        ),
                        item.image.reference,
                        item.dimensions,
                        "; ".join(item.diagnostics),
                    ),
                    180,
                    self.open_image,
                ),
                SequenceTable(
                    "boxes",
                    (
                        "Source row",
                        "Class",
                        "Score",
                        "Original",
                        "Convention",
                        "Pixel xyxy",
                        "Location",
                        "Diagnostics",
                    ),
                    lambda: model.source.boxes if model.source else (),
                    lambda box: (
                        box.origin.row_id,
                        box.box.record.class_name,
                        box.box.record.score,
                        box.box.record.original,
                        box.box.record.coordinates,
                        box.box.xyxy,
                        f"{box.box.record.asset.path}: {box.box.record.location}",
                        "; ".join(box.box.diagnostics),
                    ),
                    170,
                    self.open_box,
                ),
                SequenceTable(
                    "issues",
                    ("Image key", "File", "Location", "Diagnostic", "Original"),
                    lambda: model.source.issues if model.source else (),
                    lambda issue: (
                        issue.image_key,
                        str(issue.path),
                        issue.location,
                        issue.message,
                        issue.original,
                    ),
                    130,
                ),
            ),
        )

    def open_image(self, index: int) -> None:
        source = self.model.source
        locator = source.images[index].locator if source else None
        if locator:
            self.open_rows((locator.origin.row_id,))

    def open_box(self, index: int) -> None:
        source = self.model.source
        if source:
            self.select(source.boxes[index])

    def render(self, frame: FrameContext) -> None:
        source = self.model.source
        if source:
            imgui.text_wrapped(
                f"{len(source.images):,} image keys · "
                f"{len(source.boxes):,} usable boxes · {len(source.issues):,} issues"
            )
            if source.error:
                imgui.text_wrapped(source.error)
        super().render(frame)


class AnnotationContent(Container):
    def __init__(
        self,
        model: AnnotationController,
        open_rows: Callable[[tuple[int, ...]], None],
        select: Callable[[AssociatedBox], None],
    ) -> None:
        self.model = model
        super().__init__(
            "annotation-content",
            (
                ColumnPicker(
                    "source",
                    "Review annotation source",
                    lambda: model.source_choices,
                    lambda: (model.source.recipe.id,) if model.source else (),
                    lambda names: model.write_view(
                        replace(model.read_view(), source_id=next(iter(names), None))
                    ),
                    SingleSelection(),
                ),
                CanvasTabs(
                    (
                        NamedTab(
                            "Sources",
                            SequenceTable(
                                "sources",
                                (
                                    "Name",
                                    "File or folder",
                                    "Format",
                                    "Description",
                                    "Error",
                                ),
                                lambda: (
                                    model.jobs.active.sources
                                    if model.jobs.active
                                    else ()
                                ),
                                lambda source: (
                                    source.recipe.name or source.recipe.id,
                                    source.recipe.path,
                                    source.recipe.format,
                                    source.catalog.description
                                    if source.catalog
                                    else "",
                                    source.error,
                                ),
                                180,
                            ),
                        ),
                        NamedTab(
                            "Associations", AssociationContent(model, open_rows, select)
                        ),
                        NamedTab(
                            "Profiles",
                            AnnotationProfileContent(model, open_rows, select),
                        ),
                    ),
                    lambda: model.read_view().tab,
                    lambda value: model.write_view(
                        replace(model.read_view(), tab=value)
                    ),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        if not self.model.read_settings().sources:
            return
        imgui.separator_text("Annotations")
        imgui.text_wrapped(self.model.jobs.message)
        if self.model.jobs.active:
            super().render(frame)
