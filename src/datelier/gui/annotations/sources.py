"""Draft source forms share typed fields, column selectors and mapping tables."""

from dataclasses import replace
from uuid import uuid4

from datelier.application.annotations.controller import AnnotationController
from datelier.application.annotations.recipes import class_names, confirm_mapping
from datelier.application.tabular import ColumnChoice, SingleSelection
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import IntegerField, TextField
from datelier.gui.components.groups import Collapsible, Conditional
from datelier.gui.components.tables import SequenceTable
from datelier.inspection.annotations.settings import AnnotationSource, ImageMatch
from datelier.inspection.annotations.types import AnnotationFormat, BoxCoordinates


class SourceForm(Container):
    def __init__(self, model: AnnotationController) -> None:
        self.model = model
        self.draft = AnnotationSource(uuid4().hex, "")
        self.classes = self.mapping_key = ""
        self.mapping_row = 0
        self._observed: str | None = None
        fields = StateFields(
            lambda: self.draft, lambda value: setattr(self, "draft", value)
        )
        super().__init__(
            "annotation-source",
            (
                ColumnPicker(
                    "sources",
                    "Edit source",
                    self.sources,
                    self.selected,
                    self.choose,
                    SingleSelection(),
                ),
                CommandButton("new", "New source draft", self.new),
                fields.text(
                    "name",
                    "Source name",
                    lambda s: s.name,
                    lambda s, v: replace(s, name=v),
                ),
                fields.text(
                    "path",
                    "Annotation file or folder",
                    lambda s: s.path,
                    lambda s, v: replace(s, path=v),
                ),
                fields.choice(
                    "format",
                    "Annotation format",
                    tuple(AnnotationFormat),
                    lambda s: s.format,
                    lambda s, v: replace(s, format=v),
                ),
                fields.choice(
                    "match",
                    "Match images by",
                    tuple(ImageMatch),
                    lambda s: s.match,
                    lambda s, v: replace(s, match=v),
                ),
                Conditional(
                    "key",
                    lambda: self.draft.match == ImageMatch.COLUMN,
                    (
                        ColumnPicker(
                            "column",
                            "Image key column",
                            lambda: model.columns,
                            lambda: (
                                (self.draft.key_column,)
                                if self.draft.key_column
                                else ()
                            ),
                            lambda names: setattr(
                                self,
                                "draft",
                                replace(self.draft, key_column=next(iter(names), None)),
                            ),
                            SingleSelection(),
                        ),
                    ),
                ),
                Conditional(
                    "root",
                    lambda: self.draft.match == ImageMatch.PATH,
                    (
                        fields.text(
                            "image-root",
                            "Annotation image root",
                            lambda s: s.image_root or "",
                            lambda s, v: replace(s, image_root=v or None),
                        ),
                    ),
                ),
                Conditional(
                    "voc",
                    lambda: self.draft.format == AnnotationFormat.VOC,
                    (
                        fields.choice(
                            "convention",
                            "VOC coordinates",
                            (BoxCoordinates.VOC, BoxCoordinates.EDGES),
                            lambda s: s.convention,
                            lambda s, v: replace(s, convention=v),
                        ),
                    ),
                ),
                Conditional(
                    "yolo",
                    lambda: (
                        self.draft.format
                        in (AnnotationFormat.YOLO, AnnotationFormat.ULTRALYTICS)
                    ),
                    (
                        fields.boolean(
                            "scores",
                            "Trailing confidence scores",
                            lambda s: s.scores,
                            lambda s, v: replace(s, scores=v),
                        ),
                    ),
                ),
                Conditional(
                    "manifest",
                    lambda: self.draft.format == AnnotationFormat.ULTRALYTICS,
                    (
                        fields.text(
                            "dataset-root",
                            "Dataset root override",
                            lambda s: s.dataset_root or "",
                            lambda s, v: replace(s, dataset_root=v or None),
                        ),
                    ),
                ),
                Conditional(
                    "classes",
                    lambda: self.draft.format == AnnotationFormat.YOLO,
                    (
                        Collapsible(
                            "names",
                            "Class IDs and names",
                            (
                                TextField(
                                    "names",
                                    "One ID and name per line",
                                    lambda: self.classes,
                                    lambda value: setattr(self, "classes", value),
                                    True,
                                ),
                                CommandButton(
                                    "apply",
                                    "Apply class names to draft",
                                    self.apply_classes,
                                ),
                            ),
                        ),
                    ),
                ),
                Collapsible(
                    "mappings",
                    "Explicit image mappings",
                    (
                        TextField(
                            "key",
                            "Annotation image key",
                            lambda: self.mapping_key,
                            lambda value: setattr(self, "mapping_key", value),
                        ),
                        IntegerField(
                            "row",
                            "Stable source row ID (0-based)",
                            lambda: self.mapping_row,
                            lambda value: setattr(self, "mapping_row", value),
                        ),
                        CommandButton(
                            "confirm", "Confirm row mapping in draft", self.confirm
                        ),
                        SequenceTable(
                            "mappings",
                            ("Image key", "Source row", "Verified reference"),
                            lambda: self.draft.mappings,
                            lambda item: (
                                item.image_key,
                                item.row_id,
                                item.expected_key,
                            ),
                            130,
                            lambda index: self.remove_mapping(index),
                            "Remove",
                        ),
                    ),
                ),
                CommandButton(
                    "apply",
                    "Apply annotation source",
                    lambda: model.apply_source(self.draft),
                ),
                CommandButton(
                    "remove",
                    "Remove source",
                    lambda: model.remove_source(self.draft.id),
                    lambda: any(
                        s.id == self.draft.id for s in model.read_settings().sources
                    ),
                ),
            ),
        )

    def sources(self) -> tuple[ColumnChoice, ...]:
        return tuple(
            ColumnChoice(s.id, s.format.value, label=s.name or s.id)
            for s in self.model.read_settings().sources
        )

    def selected(self) -> tuple[str, ...]:
        return (self._observed,) if self._observed else ()

    def choose(self, identities: tuple[str, ...]) -> None:
        identity = next(iter(identities), None)
        self.model.write_view(replace(self.model.read_view(), source_id=identity))
        self._observed = None

    def new(self) -> None:
        self.model.write_view(replace(self.model.read_view(), source_id=None))
        self._observed = None
        self.draft = AnnotationSource(uuid4().hex, "")
        self.classes = self.mapping_key = ""
        self.mapping_row = 0

    def apply_classes(self) -> None:
        self.draft = replace(self.draft, classes=class_names(self.classes))

    def confirm(self) -> None:
        self.draft = confirm_mapping(self.draft, self.mapping_key, self.mapping_row)

    def remove_mapping(self, index: int) -> None:
        self.draft = replace(
            self.draft,
            mappings=tuple(
                item for i, item in enumerate(self.draft.mappings) if i != index
            ),
        )

    def render(self, frame: FrameContext) -> None:
        identity = self.model.read_view().source_id
        if identity != self._observed and identity is not None:
            source = next(
                (s for s in self.model.read_settings().sources if s.id == identity),
                None,
            )
            if source:
                self.draft, self._observed = source, identity
                self.classes = "\n".join(f"{c.id} {c.name}" for c in source.classes)
        super().render(frame)
