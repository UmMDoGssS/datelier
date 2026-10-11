"""Explicit file/folder readers, preserving per-file and directory-scope evidence."""

import os
from concurrent.futures import CancelledError
from dataclasses import replace
from pathlib import Path
from threading import Event

from datelier.inspection.annotations.settings import AnnotationSource
from datelier.inspection.annotations.types import (
    AnnotationCatalog,
    AnnotationClass,
    AnnotationFormat,
    AnnotationImage,
    AnnotationIssue,
    BoxRecord,
)
from datelier.inspection.references import AssetIdentity
from datelier.io.annotations.manifest_paths import local_path
from datelier.io.annotations.readers import (
    read_coco,
    read_ultralytics,
    read_voc,
    read_yolo,
)
from datelier.io.annotations.source import verify_sources


def read_annotation_file(source: AnnotationSource, path: Path) -> AnnotationCatalog:
    match source.format:
        case AnnotationFormat.VOC:
            return read_voc(path, source.convention)
        case AnnotationFormat.YOLO:
            return read_yolo(path, classes=source.classes, scores=source.scores)
        case AnnotationFormat.COCO:
            return read_coco(path)
        case AnnotationFormat.ULTRALYTICS:
            return read_ultralytics(
                path,
                root_override=local_path(source.dataset_root, path.parent)
                if source.dataset_root
                else None,
                scores=source.scores,
            )


def _members(path: Path, suffix: str) -> tuple[Path, ...]:
    result: list[Path] = []

    def fail(error: OSError) -> None:
        raise error

    for directory, folders, files in os.walk(path, followlinks=False, onerror=fail):
        folders[:] = sorted(
            folder
            for folder in folders
            if folder not in (".git", ".venv", "node_modules")
        )
        result.extend(
            Path(directory) / name
            for name in sorted(files)
            if Path(name).suffix.lower() == suffix
        )
    return tuple(sorted(result))


def load_annotations(source: AnnotationSource, stop: Event) -> AnnotationCatalog:
    source.validate()
    if stop.is_set():
        raise CancelledError("Annotation reading abandoned")
    path = Path(source.path).expanduser().resolve()
    if not path.is_dir():
        return read_annotation_file(source, path)
    if source.format not in (AnnotationFormat.VOC, AnnotationFormat.YOLO):
        raise ValueError("Choose one COCO JSON or Ultralytics manifest file")
    members = _members(
        path, ".xml" if source.format == AnnotationFormat.VOC else ".txt"
    )
    images: list[AnnotationImage] = []
    boxes: list[BoxRecord] = []
    classes: dict[int | str, AnnotationClass] = {}
    issues: list[AnnotationIssue] = []
    assets: list[AssetIdentity] = []
    for member in members:
        if stop.is_set():
            raise CancelledError("Annotation reading abandoned")
        key = member.relative_to(path).with_suffix("").as_posix()
        try:
            stat = member.stat()
            # Failed files still belong to the command's input snapshot.
            assets.append(AssetIdentity(member, stat.st_size, stat.st_mtime_ns))
            catalog = read_annotation_file(source, member)
            images.extend(replace(image, key=key) for image in catalog.images)
            boxes.extend(replace(box, image_key=key) for box in catalog.boxes)
            issues.extend(replace(issue, image_key=key) for issue in catalog.issues)
            classes.update((item.id, item) for item in catalog.classes)
            assets.extend(catalog.sources)
        except (ValueError, OSError, UnicodeError) as error:
            issues.append(AnnotationIssue(member, "File", str(error), key))
    if (
        _members(path, ".xml" if source.format == AnnotationFormat.VOC else ".txt")
        != members
    ):
        raise ValueError("Annotation directory membership changed; reload")
    verify_sources(assets)
    return AnnotationCatalog(
        source.format,
        tuple(assets),
        tuple(images),
        tuple(boxes),
        tuple(classes.values()),
        tuple(issues),
        "Directory keys retain relative label paths; "
        "original file provenance preserved",
    )
