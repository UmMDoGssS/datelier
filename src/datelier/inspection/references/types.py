"""Serializable reference recipes and immutable worker results."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from datelier.core.column_roles import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TEXT_EXTENSIONS,
)


@dataclass(frozen=True)
class ReferenceMapping:
    column: str
    value: str
    path: str


@dataclass(frozen=True)
class ReferenceSettings:
    roots: tuple[str, ...] = ()  # Empty selects source directory and parent's subtree.
    extensions: tuple[str, ...] = (
        *IMAGE_EXTENSIONS,
        *AUDIO_EXTENSIONS,
        *TEXT_EXTENSIONS,
    )
    mappings: tuple[ReferenceMapping, ...] = ()
    thumbnail_size: int = 128
    cpu_bytes: int = 16 * 1024 * 1024
    gpu_bytes: int = 8 * 1024 * 1024

    def validate(self) -> None:
        if not 32 <= self.thumbnail_size <= 512:
            raise ValueError("Thumbnail size must be between 32 and 512 pixels")
        if min(self.cpu_bytes, self.gpu_bytes) < 1024 * 1024:
            raise ValueError("Preview caches require at least 1 MiB")
        if any(not e.startswith(".") or e.lower() != e for e in self.extensions):
            raise ValueError("Extension filters must be lowercase suffixes with a dot")
        if len({(m.column, m.value) for m in self.mappings}) != len(self.mappings):
            raise ValueError("Choose one mapping per column/value")


@dataclass(frozen=True)
class AssetIdentity:
    path: Path
    size: int
    modified_ns: int


@dataclass(frozen=True)
class Resolution:
    value: str
    asset: AssetIdentity | None = None
    candidates: tuple[Path, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class AssetPreview:
    asset: AssetIdentity
    rgba: NDArray[np.uint8] | None = None
    text: str = ""
    description: str = ""
    message: str = ""

    @property
    def retained_bytes(self) -> int:
        return (self.rgba.nbytes if self.rgba is not None else 0) + len(
            self.text.encode()
        )
