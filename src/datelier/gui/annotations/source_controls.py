"""Finite local source, convention and image-key options; no file reads."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.gui.annotations.recipes import class_names, confirm_mapping
from datelier.inspection.annotations.settings import AnnotationSource, ImageMatch
from datelier.inspection.annotations.types import AnnotationFormat, BoxCoordinates


class SourceControls:
    def __init__(self) -> None:
        self.classes = ""
        self.mapping_key = ""
        self.mapping_row = 0
        self.message = ""
        self._classes: tuple[object, ...] | None = None

    def show(
        self, source: AnnotationSource, columns: tuple[str, ...]
    ) -> AnnotationSource:
        _, name = imgui.input_text("Source name", source.name)
        _, path = imgui.input_text("Annotation file or folder", source.path)
        formats = list(AnnotationFormat)
        _, choice = imgui.combo(
            "Annotation format",
            formats.index(source.format),
            [item.value for item in formats],
        )
        source = replace(source, name=name, path=path, format=formats[choice])
        matches = list(ImageMatch)
        _, choice = imgui.combo(
            "Match images by",
            matches.index(source.match),
            [item.value for item in matches],
        )
        source = replace(source, match=matches[choice])
        if source.match == ImageMatch.COLUMN:
            names = ["Choose a key column", *columns]
            current = (
                names.index(source.key_column) if source.key_column in names else 0
            )
            _, choice = imgui.combo("Image key field", current, names)
            source = replace(source, key_column=names[choice] if choice else None)
            imgui.text_wrapped(
                "Annotation image IDs/relative label keys match scalar field values."
            )
        if source.match == ImageMatch.PATH:
            _, root = imgui.input_text("Annotation image root", source.image_root or "")
            source = replace(source, image_root=root or None)
            imgui.text_wrapped(
                "Relative roots use the annotation file/folder; "
                "cells keep their original references."
            )
        if source.format == AnnotationFormat.VOC:
            conventions = [BoxCoordinates.VOC, BoxCoordinates.EDGES]
            current = (
                conventions.index(source.convention)
                if source.convention in conventions
                else 0
            )
            _, choice = imgui.combo(
                "VOC coordinates", current, [item.value for item in conventions]
            )
            source = replace(source, convention=conventions[choice])
        elif source.format in (AnnotationFormat.YOLO, AnnotationFormat.ULTRALYTICS):
            imgui.text_wrapped(
                "Normalized centre x/y and width/height use original image dimensions."
            )
            _, scores = imgui.checkbox("Trailing confidence scores", source.scores)
            source = replace(source, scores=scores)
            if source.format == AnnotationFormat.ULTRALYTICS:
                _, root = imgui.input_text(
                    "Dataset root override", source.dataset_root or ""
                )
                source = replace(source, dataset_root=root or None)
                imgui.text_wrapped(
                    "Local manifests only. Relative roots use the manifest "
                    "directory. Download fields are never executed."
                )
            elif imgui.tree_node("YOLO class names"):
                if self._classes != source.classes:
                    self.classes = "\n".join(
                        f"{item.id} {item.name}" for item in source.classes
                    )
                    self._classes = source.classes
                _, self.classes = imgui.input_text_multiline(
                    "Class IDs and names", self.classes, (0, 80)
                )
                if imgui.button("Apply class names"):
                    try:
                        source = replace(source, classes=class_names(self.classes))
                        self._classes, self.message = source.classes, ""
                    except ValueError as error:
                        self.message = str(error)
                imgui.text_wrapped(
                    "One ID and name per line, e.g. 0 person. "
                    "Empty means retain numeric IDs."
                )
                imgui.tree_pop()
        else:
            imgui.text_wrapped(
                "COCO uses image/category IDs and 0-based pixel x/y/width/height."
            )
        if imgui.tree_node(f"Explicit image mappings ({len(source.mappings)})"):
            _, self.mapping_key = imgui.input_text(
                "Annotation image key", self.mapping_key
            )
            _, self.mapping_row = imgui.input_int("Mapped source row", self.mapping_row)
            if imgui.button("Confirm row mapping"):
                try:
                    source = confirm_mapping(source, self.mapping_key, self.mapping_row)
                    self.message = (
                        "Mapping set. Load/associate to verify its image reference."
                    )
                except ValueError as error:
                    self.message = str(error)
            imgui.text_wrapped(
                "Use stable Source row IDs, independent of table sorting. "
                "Confirming again replaces a changed-reference pin."
            )
            if imgui.begin_child("Saved row mappings", (0, 100)):
                clipper = imgui.ListClipper()
                clipper.begin(len(source.mappings))
                removed: str | None = None
                while clipper.step():
                    for index in range(clipper.display_start, clipper.display_end):
                        item = source.mappings[index]
                        imgui.push_id(index)
                        if imgui.small_button("Remove"):
                            removed = item.image_key
                        imgui.same_line()
                        imgui.text_unformatted(
                            f"{item.image_key} → source row {item.row_id} · "
                            + ("verified" if item.expected_key else "unverified")
                        )
                        imgui.pop_id()
                if removed is not None:
                    source = replace(
                        source,
                        mappings=tuple(
                            item
                            for item in source.mappings
                            if item.image_key != removed
                        ),
                    )
            imgui.end_child()
            imgui.tree_pop()
        if self.message:
            imgui.text_wrapped(self.message)
        return source
