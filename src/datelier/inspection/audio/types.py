"""Audio source identity, original signal metadata and bounded sample windows."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from datelier.core.dataset import DatasetRevision
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.references.types import AssetIdentity


@dataclass(frozen=True)
class AudioOrigin:
    file_id: str
    view_name: str
    revision: DatasetRevision
    row_id: int
    column: str


@dataclass(frozen=True)
class AudioLocator:
    origin: AudioOrigin
    asset: AssetIdentity | None = None
    catalog: ArrayCatalog | None = None
    mapping: ArrayRecordMapping | None = None
    source_index: int | None = None


def validate_sample_rate(rate: int | None) -> None:
    if rate is not None and (isinstance(rate, bool) or not 1 <= rate <= 768000):
        raise ValueError("Array sample rate must be between 1 and 768000 Hz")


@dataclass(frozen=True)
class AudioMetadata:
    frames: int
    channels: int
    sample_rate: int | None
    dtype: np.dtype[np.generic]
    format: str
    subtype: str
    units: str
    description: str

    @property
    def duration(self) -> float | None:
        return self.frames / self.sample_rate if self.sample_rate else None

    def require_rate(self) -> int:
        if self.sample_rate is None:
            raise ValueError("Configure the array sample rate before signal inspection")
        return self.sample_rate


@dataclass(frozen=True)
class AudioRange:
    start: int = 0
    stop: int | None = None

    def bounds(self, frames: int) -> tuple[int, int]:
        if self.start < 0 or self.stop is not None and self.stop < self.start:
            raise ValueError("Audio range needs ordered nonnegative frame positions")
        if self.start > frames or self.stop is not None and self.stop > frames:
            raise ValueError("Audio range is outside the original signal")
        return self.start, frames if self.stop is None else self.stop


@dataclass(frozen=True)
class AudioBlock:
    start: int
    samples: NDArray[np.generic]  # frames × channels; source values, read-only.


@dataclass(frozen=True)
class PreparedAudio:
    locator: AudioLocator
    metadata: AudioMetadata
    range: AudioRange
    raw: NDArray[np.generic]

    @property
    def retained_bytes(self) -> int:
        return self.raw.nbytes
