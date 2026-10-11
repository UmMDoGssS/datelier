"""Read-only annotation snapshots and narrow scalar parsing boundaries."""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from math import isfinite
from pathlib import Path
from typing import BinaryIO

from datelier.inspection.references import AssetIdentity


@contextmanager
def annotation_source(path: Path) -> Iterator[tuple[AssetIdentity, BinaryIO]]:
    path = path.expanduser().resolve()
    before = path.stat()
    asset = AssetIdentity(path, before.st_size, before.st_mtime_ns)
    with path.open("rb") as stream:
        yield asset, stream
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
    ):
        raise ValueError("Annotation source changed while reading; retry")


def finite_number(text: str) -> float:
    value = float(text)
    if not isfinite(value):
        raise ValueError("Annotation values must be finite")
    return value


def coordinates(values: list[str]) -> tuple[float, float, float, float]:
    if len(values) != 4:
        raise ValueError("Detection boxes require four coordinates")
    a, b, c, d = (finite_number(value) for value in values)
    return a, b, c, d


def verify_sources(sources: Iterable[AssetIdentity]) -> None:
    for asset in sources:
        stat = asset.path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (asset.size, asset.modified_ns):
            raise ValueError(
                f"Annotation/image source changed during command: {asset.path}"
            )
