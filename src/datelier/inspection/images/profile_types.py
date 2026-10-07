"""Explicit collection scope and source-aligned scalar image profile results."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from threading import Lock

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.core.dataset import DatasetRevision, SourceReference
from datelier.inspection.arrays.mapping import ArrayRecordMapping


class ImageScopeMode(StrEnum):
    COLLECTION = "All current rows"
    RANGE = "Row range"
    SELECTION = "Linked selection"
    RANDOM = "Seeded random sample"


class PixelScope(StrEnum):
    EXACT = "All original pixels"
    SAMPLE = "Seeded pixel sample"


@dataclass(frozen=True)
class ImageScope:
    mode: ImageScopeMode = ImageScopeMode.COLLECTION
    start: int = 1
    count: int = 100
    seed: int = 42

    def validate(self) -> None:
        if min(self.start, self.count) < 1 or not 0 <= self.seed < 2**32:
            raise ValueError("Image scope needs positive range/count and a 32-bit seed")


@dataclass(frozen=True)
class ImageProfileSettings:
    column: str | None = None
    scope: ImageScope = ImageScope()
    pixels: PixelScope = PixelScope.EXACT
    pixel_count: int = 100_000
    pixel_seed: int = 42
    bins: int = 32

    def validate(self) -> None:
        self.scope.validate()
        if self.pixel_count < 1 or not 0 <= self.pixel_seed < 2**32:
            raise ValueError("Pixel samples need positive counts and a 32-bit seed")
        if not 1 <= self.bins <= 256:
            raise ValueError("Image profiles require 1–256 bins")


class ImageProgress:
    def __init__(self) -> None:
        self._lock = Lock()
        self._value = ("", 0, 0)

    @property
    def value(self) -> tuple[str, int, int]:
        with self._lock:
            return self._value

    def update(self, phase: str, done: int, total: int) -> None:
        with self._lock:
            self._value = phase, done, total


@dataclass(frozen=True)
class ChannelKey:
    mode: str
    name: str
    dtype: str

    @property
    def label(self) -> str:
        return f"{self.mode} · {self.name} · {np.dtype(self.dtype)}"

    @property
    def family_label(self) -> str:
        return f"{self.mode} · {np.dtype(self.dtype)}"


type ImageBounds = Mapping[ChannelKey, tuple[int | float, int | float]]


@dataclass(frozen=True)
class ChannelSummary:
    key: ChannelKey
    values: int
    finite: int
    nonfinite: int
    minimum: int | float | None
    maximum: int | float | None
    mean: float | None
    stddev: float | None


@dataclass(frozen=True)
class ImageHistogram:
    label: str
    edges: NDArray[np.float64]
    counts: NDArray[np.float64]
    scaled: bool = False
    minimum: int | float | None = None
    maximum: int | float | None = None
    plot_x: NDArray[np.float64] | None = None
    plot_counts: NDArray[np.float64] | None = None
    normalized_plot_x: NDArray[np.float64] | None = None


@dataclass(frozen=True)
class ImageProfile:
    file_id: str
    view_name: str
    revision: DatasetRevision
    source: SourceReference
    settings: ImageProfileSettings
    mapping: ArrayRecordMapping | None
    available_records: int
    records: pl.DataFrame
    channel_records: pl.DataFrame
    summaries: tuple[ChannelSummary, ...]
    dimensions: tuple[ImageHistogram, ...]
    channels: tuple[ImageHistogram, ...]
    ready: int
    nulls: int
    unresolved: int
    failures: int
    total_pixels: int
    profiled_pixels: int
    dimension_summaries: tuple[ChannelSummary, ...] = ()

    @property
    def sampled_pixels(self) -> bool:
        return self.profiled_pixels < self.total_pixels

    @property
    def retained_bytes(self) -> int:
        return int(
            self.records.estimated_size() + self.channel_records.estimated_size()
        ) + sum(
            chart.edges.nbytes
            + chart.counts.nbytes
            + (chart.plot_x.nbytes if chart.plot_x is not None else 0)
            + (chart.plot_counts.nbytes if chart.plot_counts is not None else 0)
            + (
                chart.normalized_plot_x.nbytes
                if chart.normalized_plot_x is not None
                else 0
            )
            for chart in (*self.dimensions, *self.channels)
        )
