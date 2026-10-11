"""Worker target-key indices, preserving original source row identity."""

from concurrent.futures import CancelledError
from dataclasses import dataclass
from pathlib import Path
from threading import Event

import polars as pl

from datelier.core import Dataset
from datelier.inspection.annotations.settings import AnnotationSource, ImageMatch
from datelier.inspection.annotations.types import AnnotationImage
from datelier.inspection.arrays import ArrayCatalog, ArrayRecordMapping
from datelier.inspection.images.decoding.sources import locate_image
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.references.index import ReferenceIndex
from datelier.io.annotations.manifest_paths import local_path


@dataclass(frozen=True)
class TargetIndex:
    positions: dict[int, int]
    keys: dict[int, str]
    candidates: dict[str, tuple[int, ...]]
    pins: dict[int, str]


def source_key(source: AnnotationSource, image: AnnotationImage) -> str:
    if source.match == ImageMatch.COLUMN:
        return image.key
    if source.match == ImageMatch.FILENAME:
        return Path(image.reference).name
    if source.match == ImageMatch.STEM:
        return Path(image.reference).stem
    root = Path(source.path).expanduser().resolve()
    if not root.is_dir():
        root = root.parent
    if source.image_root:
        root = local_path(source.image_root, root)
    return str(local_path(image.reference, root))


def target_index(
    dataset: Dataset,
    source: AnnotationSource,
    column: str,
    file_id: str,
    view_name: str,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    catalog: ArrayCatalog | None,
    mapping: ArrayRecordMapping | None,
    stop: Event,
) -> TargetIndex:
    key_column = source.key_column if source.match == ImageMatch.COLUMN else column
    if key_column is None or key_column not in dataset.table.columns:
        raise ValueError(
            "Choose the target image/key column; mapped arrays use an image key column"
        )
    if (
        source.match != ImageMatch.COLUMN
        and dataset.table.schema[key_column] != pl.String
    ):
        raise ValueError(
            "Filename/path association requires a physical String image field"
        )
    positions: dict[int, int] = {}
    keys: dict[int, str] = {}
    grouped: dict[str, list[int]] = {}
    pins: dict[int, str] = {}
    image_values = dataset.table[column] if column in dataset.table.columns else None
    base = (
        dataset.source.path
        if dataset.source.path.is_dir()
        else dataset.source.path.parent
    )
    for position, (row_id, value) in enumerate(
        zip(dataset.row_ids, dataset.table[key_column], strict=True)
    ):
        if position % 512 == 0 and stop.wait(0.001):
            raise CancelledError("Annotation key preparation abandoned")
        row = int(row_id)
        positions[row] = position
        if value is None:
            continue
        reference = (
            str(image_values[position])
            if image_values is not None and image_values[position] is not None
            else None
        )
        if reference is not None:
            physical = Path(reference)
            if physical.is_absolute() and physical.is_relative_to(base):
                reference = physical.relative_to(base).as_posix()
        pins[row] = repr((reference if key_column == column else str(value), reference))
        if source.match == ImageMatch.COLUMN:
            key = str(value)
        elif source.match == ImageMatch.FILENAME:
            key = Path(str(value)).name
        elif source.match == ImageMatch.STEM:
            key = Path(str(value)).stem
        else:
            try:
                locator = locate_image(
                    dataset,
                    file_id,
                    view_name,
                    column,
                    position,
                    references,
                    index,
                    catalog,
                    mapping,
                )
                if locator.asset is None:
                    raise ValueError("Mapped arrays require an image key column")
                key = str(locator.asset.path)
            except ValueError, OSError:
                continue
        keys[row] = key
        grouped.setdefault(key, []).append(row)
    return TargetIndex(
        positions, keys, {key: tuple(rows) for key, rows in grouped.items()}, pins
    )
