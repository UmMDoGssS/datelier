"""Local YAML/YOLO dataset inspection; manifests remain data and never execute."""

from dataclasses import replace
from pathlib import Path

from datelier.inspection.annotations.types import (
    AnnotationCatalog,
    AnnotationClass,
    AnnotationFormat,
    AnnotationImage,
    AnnotationIssue,
    BoxRecord,
)
from datelier.inspection.images.decoding.sources import file_metadata
from datelier.inspection.references.types import AssetIdentity
from datelier.io.annotations.manifest_paths import label_path, local_path, split_images
from datelier.io.annotations.source import annotation_source, verify_sources
from datelier.io.annotations.values import integer, mapping, text
from datelier.io.annotations.yaml_source import decode_manifest
from datelier.io.annotations.yolo import read_yolo


def manifest_classes(value: dict[str, object]) -> tuple[AnnotationClass, ...]:
    names = value.get("names")
    if isinstance(names, list):
        classes = tuple(
            AnnotationClass(i, text(name, "Class name")) for i, name in enumerate(names)
        )
    elif isinstance(names, dict):
        ids: dict[int, AnnotationClass] = {}
        for key, name in names.items():
            class_id = integer(
                int(key) if isinstance(key, str) and key.isdecimal() else key,
                "Class id",
            )
            if class_id in ids:
                raise ValueError(f"Duplicate normalized class ID {class_id}")
            ids[class_id] = AnnotationClass(class_id, text(name, "Class name"))
        classes = tuple(ids.values())
    elif names is None and "nc" in value:
        integer(value["nc"], "nc", positive=True)
        # A declared count need not allocate names for unused classes.
        return ()
    else:
        raise ValueError("Manifest requires a class names list/map or nc")
    if not classes or {item.id for item in classes} != set(range(len(classes))):
        raise ValueError("Ultralytics class IDs must cover contiguous zero-based names")
    if "nc" in value and integer(value["nc"], "nc", positive=True) != len(classes):
        raise ValueError("Manifest nc and class names count must agree")
    return classes


def read_ultralytics(
    path: Path, *, root_override: Path | None = None, scores: bool = False
) -> AnnotationCatalog:
    with annotation_source(path) as (asset, stream):
        value = mapping(
            decode_manifest(stream.read().decode("utf-8-sig")), "Detection manifest"
        )
        root = (
            root_override.expanduser().resolve()
            if root_override
            else local_path(
                text(value.get("path", "."), "Dataset root"), asset.path.parent
            )
        )
        classes = manifest_classes(value)
        class_count = (
            integer(value["nc"], "nc", positive=True) if "nc" in value else len(classes)
        )
        images: dict[Path, AnnotationImage] = {}
        boxes: list[BoxRecord] = []
        issues: list[AnnotationIssue] = []
        sources: dict[Path, AssetIdentity] = {asset.path: asset}
        splits = tuple(
            name
            for name in ("train", "val", "test", "minival")
            if value.get(name) is not None
        )
        if not splits:
            raise ValueError("Manifest needs at least one local image split")
        if "download" in value:
            issues.append(
                AnnotationIssue(
                    asset.path,
                    "download",
                    "Download field retained in source; "
                    "local inspection does not execute it",
                )
            )
        for split in splits:
            try:
                members, lists = split_images(value[split], root)
                sources.update((source.path, source) for source in lists)
            except (ValueError, OSError, UnicodeError) as error:
                issues.append(AnnotationIssue(asset.path, split, str(error)))
                continue
            for image in members:
                key = (
                    image.relative_to(root).as_posix()
                    if image.is_relative_to(root)
                    else str(image)
                )
                if image in images:
                    previous = images[image]
                    images[image] = replace(
                        previous, split=previous.split + ", " + split
                    )
                    issues.append(
                        AnnotationIssue(
                            asset.path,
                            split,
                            "Repeated image entry; shared boxes counted once",
                            key,
                            str(image),
                        )
                    )
                    continue
                dimensions = None
                try:
                    stat = image.stat()
                    image_asset = AssetIdentity(image, stat.st_size, stat.st_mtime_ns)
                    metadata = file_metadata(image_asset)
                    dimensions = metadata.source_width, metadata.source_height
                    sources[image] = image_asset
                except Exception as error:
                    # Pillow has format-specific failures and decompression-bomb
                    # exceptions; one bad header must not discard other images.
                    issues.append(
                        AnnotationIssue(image, "Image header", str(error), key)
                    )
                labels = label_path(image)
                status = "Missing"
                try:
                    labels_catalog = read_yolo(
                        labels,
                        image_key=key,
                        classes=classes,
                        scores=scores,
                        class_count=class_count,
                    )
                    boxes.extend(labels_catalog.boxes)
                    issues.extend(labels_catalog.issues)
                    sources.update(
                        (source.path, source) for source in labels_catalog.sources
                    )
                    status = (
                        "Present"
                        if labels_catalog.boxes
                        else "Invalid"
                        if labels_catalog.issues
                        else "Empty"
                    )
                except FileNotFoundError:
                    issues.append(
                        AnnotationIssue(
                            labels,
                            "Label file",
                            "No label file; objects are unknown, not inferred negative",
                            key,
                        )
                    )
                except (ValueError, OSError, UnicodeError) as error:
                    status = "Unreadable"
                    issues.append(
                        AnnotationIssue(labels, "Label file", str(error), key)
                    )
                images[image] = AnnotationImage(
                    key, str(image), dimensions, split, labels, status
                )
        owners: dict[Path, list[Path]] = {}
        for image, info in images.items():
            if info.label_path is not None:
                owners.setdefault(info.label_path, []).append(image)
        ambiguous_keys: set[str] = set()
        for labels, candidates in owners.items():
            if len(candidates) > 1:
                for image in candidates:
                    info = images[image]
                    images[image] = replace(info, label_status="Ambiguous")
                    ambiguous_keys.add(info.key)
                    issues.append(
                        AnnotationIssue(
                            labels,
                            "Label association",
                            "One label path matches multiple images; "
                            "explicit association required",
                            info.key,
                        )
                    )
        boxes = [
            replace(
                box,
                diagnostics=(*box.diagnostics, "Ambiguous manifest label association"),
            )
            if box.image_key in ambiguous_keys
            else box
            for box in boxes
        ]
        verify_sources((*sources.values(), *(box.asset for box in boxes)))
    return AnnotationCatalog(
        AnnotationFormat.ULTRALYTICS,
        tuple(sources.values()),
        tuple(images.values()),
        tuple(boxes),
        classes
        or tuple(
            {
                box.class_id: AnnotationClass(box.class_id, box.class_name)
                for box in boxes
            }.values()
        ),
        tuple(issues),
        f"Dataset root {root}; manifest-relative default; "
        "original source dimensions; normalized YOLO boxes",
        class_count,
    )
